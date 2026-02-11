from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Camera, PeopleEvent


@dataclass
class ChannelState:
    camera_name: str
    api_channel: int
    last_entered: int = 0
    last_exited: int = 0
    occupancy: int = 0
    # Numero di persone presenti in area (ManNumDetection / InsideSubtotal.Total)
    inside_total: int = 0


class PeopleCountingService:
    """
    Mantiene lo stato in memoria e persiste gli eventi nel DB.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._channels: Dict[int, ChannelState] = {}

    async def init_from_db(self, session: AsyncSession) -> None:
        """
        Carica/mappa le camere e inizializza lo stato.
        Se le camere D4/D6 non esistono, le crea.
        """
        # Ensure cameras exist
        cameras = (await session.scalars(select(Camera))).all()
        by_name = {c.name: c for c in cameras}

        d4 = by_name.get("D4")
        if d4 is None:
            d4 = Camera(
                name="D4",
                api_channel=self.settings.camera_d4_channel,
            )
            session.add(d4)
        else:
            # Aggiorna api_channel se è cambiato in configurazione
            if d4.api_channel != self.settings.camera_d4_channel:
                d4.api_channel = self.settings.camera_d4_channel
                session.add(d4)

        d6 = by_name.get("D6")
        if d6 is None:
            d6 = Camera(
                name="D6",
                api_channel=self.settings.camera_d6_channel,
            )
            session.add(d6)
        else:
            if d6.api_channel != self.settings.camera_d6_channel:
                d6.api_channel = self.settings.camera_d6_channel
                session.add(d6)

        await session.flush()

        self._channels = {
            d4.api_channel: ChannelState("D4", d4.api_channel),
            d6.api_channel: ChannelState("D6", d6.api_channel),
        }

    def get_channels(self) -> Dict[int, ChannelState]:
        return self._channels

    async def handle_raw_totals(
        self,
        session: AsyncSession,
        *,
        api_channel: int,
        entered_total: int,
        exited_total: int,
    ) -> None:
        """
        Aggiorna lo stato dato un nuovo snapshot dei totali proveniente dall'NVR.
        Crea uno o più PeopleEvent se ci sono variazioni.
        """
        state = self._channels.get(api_channel)
        if state is None:
            # Ignora canali non configurati
            return

        delta_enter = max(0, entered_total - state.last_entered)
        delta_exit = max(0, exited_total - state.last_exited)

        if delta_enter == 0 and delta_exit == 0:
            return

        # Aggiorna stato
        state.last_entered = entered_total
        state.last_exited = exited_total

        # Query camera id
        camera = await session.scalar(
            select(Camera).where(Camera.api_channel == api_channel)
        )
        if camera is None:
            return

        now = datetime.utcnow()

        if delta_enter > 0:
            state.occupancy += delta_enter
            event = PeopleEvent(
                timestamp=now,
                camera_id=camera.id,
                direction="ENTRATA",
                delta=delta_enter,
                entered_total=entered_total,
                exited_total=exited_total,
                occupancy_after=state.occupancy,
            )
            session.add(event)

    async def handle_inside_total(
        self,
        session: AsyncSession,
        *,
        api_channel: int,
        inside_total: int,
    ) -> None:
        """
        Aggiorna il numero di persone presenti in area (InsideSubtotal.Total)
        per il canale specificato. Non crea eventi di storico per ora.
        """
        state = self._channels.get(api_channel)
        if state is None:
            return

        state.inside_total = max(0, inside_total)

        if delta_exit > 0:
            state.occupancy = max(0, state.occupancy - delta_exit)
            event = PeopleEvent(
                timestamp=now,
                camera_id=camera.id,
                direction="USCITA",
                delta=delta_exit,
                entered_total=entered_total,
                exited_total=exited_total,
                occupancy_after=state.occupancy,
            )
            session.add(event)

    def get_presence_snapshot(self) -> dict:
        """
        Ritorna un dizionario con presenti per camera e totale.
        """
        per_camera = []
        for s in self._channels.values():
            # presenti camera = (entrati - usciti) + persone presenti in area
            presenti_camera = s.occupancy + s.inside_total
            per_camera.append(
                {
                    "camera": s.camera_name,
                    "presenti": presenti_camera,
                }
            )
        total = sum(s["presenti"] for s in per_camera)
        return {
            "timestamp": datetime.utcnow(),
            "presenti_totali": total,
            "per_camera": per_camera,
            "since_reset": None,  # opzionale: si può leggere da ResetLog
        }

    def get_debug_state(self) -> list[dict]:
        """
        Stato interno per canale: totali grezzi e occupancy.
        Utile per confrontare con i contatori visibili nella GUI Dahua.
        """
        return [
            {
                "api_channel": ch,
                "camera": s.camera_name,
                "last_entered": s.last_entered,
                "last_exited": s.last_exited,
                "occupancy": s.occupancy,
                "inside_total": s.inside_total,
            }
            for ch, s in self._channels.items()
        ]


people_service = PeopleCountingService()

