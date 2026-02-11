from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import get_session, init_db
from .people_subscriber import DahuaPeopleSubscriber, DeviceSource
from .routes import router as api_router
from .services import people_service

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown FastAPI.
    - Inizializza DB e stato.
    - Avvia le subscription verso le telecamere IP.
    """
    settings = get_settings()

    # Init DB and load cameras/state
    await init_db()
    async with get_session() as session:
        await people_service.init_from_db(session)

    async def totals_handler(api_channel: int, entered: int, exited: int) -> None:
        async with get_session() as session:
            await people_service.handle_raw_totals(
                session,
                api_channel=api_channel,
                entered_total=entered,
                exited_total=exited,
            )

    async def inside_handler(api_channel: int, inside_total: int) -> None:
        async with get_session() as session:
            await people_service.handle_inside_total(
                session,
                api_channel=api_channel,
                inside_total=inside_total,
            )

    # Definisci le sorgenti (telecamere IP) da monitorare
    sources: list[DeviceSource] = [
        DeviceSource(
            name="D4",
            host=settings.camera_d4_host,
            port=settings.camera_d4_port,
            username=settings.camera_d4_username,
            password=settings.camera_d4_password,
            logical_channel=settings.camera_d4_channel,
            attach_channel=settings.camera_d4_attach_channel,
        ),
        DeviceSource(
            name="D6",
            host=settings.camera_d6_host,
            port=settings.camera_d6_port,
            username=settings.camera_d6_username,
            password=settings.camera_d6_password,
            logical_channel=settings.camera_d6_channel,
            attach_channel=settings.camera_d6_attach_channel,
        ),
    ]

    subscriber = DahuaPeopleSubscriber(
        totals_handler=totals_handler, inside_handler=inside_handler
    )
    await subscriber.start(sources)

    logger.info(
        "People-counting backend started. Monitoring sources: %s",
        [f"{s.name}@{s.host}:{s.port} (logical_channel={s.logical_channel})" for s in sources],
    )

    try:
        yield
    finally:
        await subscriber.stop()


app = FastAPI(
    title="People Counting Backend (Dahua NVR)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)

