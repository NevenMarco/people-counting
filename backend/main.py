import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import get_session, init_db
from .people_subscriber import DahuaPeopleSubscriber, DeviceSource
from .routes import router as api_router
from .services import people_service

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def scheduler_loop():
    """
    Background task che attende l'orario di reset (es. 03:00)
    e invoca il reset dei contatori.
    """
    settings = get_settings()
    while True:
        try:
            now = datetime.now()
            target = now.replace(
                hour=settings.reset_hour,
                minute=settings.reset_minute,
                second=0,
                microsecond=0,
            )
            if target <= now:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info("Scheduler: next reset at %s (in %.1fs)", target, wait_seconds)

            await asyncio.sleep(wait_seconds)

            logger.info("Scheduler: executing daily reset...")
            async with get_session() as session:
                await people_service.reset_occupancy(session)
            logger.info("Scheduler: daily reset completed.")

        except asyncio.CancelledError:
            logger.info("Scheduler: task cancelled.")
            break
        except Exception as exc:
            logger.error("Scheduler error: %s", exc)
            # Evita loop stretto in caso di errore continuo
            await asyncio.sleep(60)


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
        [
            f"{s.name}@{s.host}:{s.port} (logical_channel={s.logical_channel})"
            for s in sources
        ],
    )

    # Avvia scheduler reset
    scheduler_task = asyncio.create_task(scheduler_loop(), name="scheduler")

    try:
        yield
    finally:
        scheduler_task.cancel()
        await subscriber.stop()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="People Counting Backend (Dahua NVR)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)

# Mount frontend config
# Check if frontend dir exists
frontend_path = os.path.join(os.getcwd(), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found at %s", frontend_path)
