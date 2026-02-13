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
    # Numero di persone presenti in area (ManNumDetection / InsideSubtotal.Total)
    inside_total: int = 0


class PeopleCountingService:
    """
    Mantiene lo stato in memoria e persiste gli eventi nel DB.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._channels: Dict[int, ChannelState] = {}
        # Offset globale per allineare il conteggio (supporta valori negativi)
        self.occupancy_offset: int = 0

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

        prev_entered = state.last_entered
        prev_exited = state.last_exited

        # Aggiorna sempre last_entered/last_exited con i valori dalla telecamera (EnteredSubtotal.Today, ExitedSubtotal.Today)
        state.last_entered = entered_total
        state.last_exited = exited_total

        delta_enter = max(0, entered_total - prev_entered)
        delta_exit = max(0, exited_total - prev_exited)

        if delta_enter == 0 and delta_exit == 0:
            return

        # Query camera id
        camera = await session.scalar(
            select(Camera).where(Camera.api_channel == api_channel)
        )
        if camera is None:
            return

        now = datetime.utcnow()

        # Totale presenti al momento dell'evento (per storico)
        total_after = self.get_presence_snapshot()["presenti_totali"]

        if delta_enter > 0:
            event = PeopleEvent(
                timestamp=now,
                camera_id=camera.id,
                direction="ENTRATA",
                delta=delta_enter,
                entered_total=entered_total,
                exited_total=exited_total,
                occupancy_after=total_after,
            )
            session.add(event)

        if delta_exit > 0:
            event = PeopleEvent(
                timestamp=now,
                camera_id=camera.id,
                direction="USCITA",
                delta=delta_exit,
                entered_total=entered_total,
                exited_total=exited_total,
                occupancy_after=total_after,
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

    def get_presence_snapshot(self) -> dict:
        """
        Ritorna un dizionario con presenti totali calcolati secondo formula:
        Total = PC1(D4) + [(In_D4 + In_D6) - (Out_D4 + Out_D6)] + Offset

        Per 'per_camera', attribuiamo il conteggio in modo convenzionale:
        D4 = PC1 + (In_D4 - Out_D4) + Offset
        D6 = (In_D6 - Out_D6)
        """
        d4_ch = self.settings.camera_d4_channel
        d6_ch = self.settings.camera_d6_channel

        d4_val = 0
        d6_val = 0

        # Calcolo componenti D4
        if d4_ch in self._channels:
            s = self._channels[d4_ch]
            # PC1 + (In - Out)
            d4_val = s.inside_total + (s.last_entered - s.last_exited)

        # Calcolo componenti D6
        if d6_ch in self._channels:
            s = self._channels[d6_ch]
            # (In - Out)
            d6_val = s.last_entered - s.last_exited

        # Totale formula base
        raw_total = d4_val + d6_val

        # Applica offset globale (lo attribuiamo visualmente a D4 per semplicità)
        final_total = raw_total + self.occupancy_offset
        d4_final = d4_val + self.occupancy_offset

        per_camera = [
            {"camera": "D4", "presenti": d4_final},
            {"camera": "D6", "presenti": d6_val},
        ]

        return {
            "timestamp": datetime.utcnow(),
            "presenti_totali": final_total,
            "per_camera": per_camera,
            "since_reset": None,
        }

    async def reset_occupancy(
        self, session: AsyncSession, reason: str = "SCHEDULED_RESET"
    ) -> None:
        """
        Resetta i contatori a 0 chiamando set_occupancy(0).
        """
        await self.set_occupancy(session, 0, reason=reason)

    def get_debug_state(self) -> list[dict]:
        """
        Stato interno per canale: totali grezzi e inside_total.
        Utile per confrontare con i contatori visibili nella GUI Dahua.
        """
        return [
            {
                "api_channel": ch,
                "camera": s.camera_name,
                "last_entered": s.last_entered,
                "last_exited": s.last_exited,
                "inside_total": s.inside_total,
            }
            for ch, s in self._channels.items()
        ]

    async def set_occupancy(
        self, session: AsyncSession, target_occupancy: int, reason: str = "MANUAL_SET"
    ) -> None:
        """
        Imposta manualmente il numero totale di presenti.
        Usa la stessa formula di get_presence_snapshot per il totale attuale
        e applica la differenza a occupancy_offset.
        """
        now = datetime.utcnow()
        from .models import ResetLog

        # Usa la stessa formula di get_presence_snapshot per coerenza
        snapshot = self.get_presence_snapshot()
        current_total = snapshot["presenti_totali"]

        diff = target_occupancy - current_total

        if diff == 0:
            return

        # Applica la correzione su occupancy_offset (unico meccanismo di correzione manuale)
        self.occupancy_offset += diff

        # Log event (usiamo D4 come riferimento per il log)
        try:
            target_channel = self.settings.camera_d4_channel
            camera = await session.scalar(
                select(Camera).where(Camera.api_channel == target_channel)
            )
            if camera:
                log_entry = ResetLog(
                    timestamp=now,
                    camera_id=camera.id,
                    reason=f"{reason}: {target_occupancy}",
                    success=True,
                )
                session.add(log_entry)
        except Exception:
            pass

        await session.flush()


people_service = PeopleCountingService()
