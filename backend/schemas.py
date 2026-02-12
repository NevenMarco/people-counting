from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class CameraPresence(BaseModel):
    camera: str
    presenti: int


class PresenceResponse(BaseModel):
    timestamp: datetime
    presenti_totali: int
    per_camera: List[CameraPresence]
    since_reset: datetime | None = None


class SetOccupancyRequest(BaseModel):
    occupancy: int
