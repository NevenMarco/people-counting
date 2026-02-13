import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .admin_routes import router as admin_router
from .admin_settings import get_effective_camera_config, load_admin_settings
from .camera_sync import fetch_camera_summary
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
        db_settings = await load_admin_settings(session)

    # Config effettiva: DB override env
    effective = get_effective_camera_config(db_settings)

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
            host=effective["camera_d4_host"],
            port=effective["camera_d4_port"],
            username=effective["camera_d4_username"],
            password=effective["camera_d4_password"],
            logical_channel=effective["camera_d4_channel"],
            attach_channel=effective["camera_d4_attach_channel"],
        ),
        DeviceSource(
            name="D6",
            host=effective["camera_d6_host"],
            port=effective["camera_d6_port"],
            username=effective["camera_d6_username"],
            password=effective["camera_d6_password"],
            logical_channel=effective["camera_d6_channel"],
            attach_channel=effective["camera_d6_attach_channel"],
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

    async def camera_sync_loop():
        """
        Sincronizza periodicamente last_entered/last_exited con getSummary
        per allineare lo stato alle telecamere (EnteredSubtotal.Today, ExitedSubtotal.Today).
        """
        sync_interval = 30
        while True:
            try:
                async with get_session() as session:
                    db_settings = await load_admin_settings(session)
                cfg = get_effective_camera_config(db_settings)
                rule_name = cfg.get("rule_area_name", "Presenti-Reception")

                # D4
                d4_data = await fetch_camera_summary(
                    host=cfg["camera_d4_host"],
                    port=cfg["camera_d4_port"],
                    username=cfg["camera_d4_username"],
                    password=cfg["camera_d4_password"],
                    channel=cfg["camera_d4_attach_channel"],
                    rule_name=rule_name,
                )
                if d4_data:
                    await totals_handler(
                        cfg["camera_d4_channel"],
                        d4_data["entered"],
                        d4_data["exited"],
                    )
                    if d4_data.get("inside") is not None:
                        await inside_handler(cfg["camera_d4_channel"], d4_data["inside"])

                # D6
                d6_data = await fetch_camera_summary(
                    host=cfg["camera_d6_host"],
                    port=cfg["camera_d6_port"],
                    username=cfg["camera_d6_username"],
                    password=cfg["camera_d6_password"],
                    channel=cfg["camera_d6_attach_channel"],
                    rule_name=rule_name,
                )
                if d6_data:
                    await totals_handler(
                        cfg["camera_d6_channel"],
                        d6_data["entered"],
                        d6_data["exited"],
                    )
                    if d6_data.get("inside") is not None:
                        await inside_handler(cfg["camera_d6_channel"], d6_data["inside"])

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Camera sync error: %s", exc)

            await asyncio.sleep(sync_interval)

    # Avvia scheduler reset e sync telecamere
    scheduler_task = asyncio.create_task(scheduler_loop(), name="scheduler")
    sync_task = asyncio.create_task(camera_sync_loop(), name="camera_sync")

    try:
        yield
    finally:
        scheduler_task.cancel()
        sync_task.cancel()
        await subscriber.stop()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="People Counting Backend (Dahua NVR)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(admin_router)

# Mount frontend config
# Check if frontend dir exists
frontend_path = os.path.join(os.getcwd(), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found at %s", frontend_path)
