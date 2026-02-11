from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .schemas import PresenceResponse, CameraPresence
from .services import people_service
from .nvr_client import get_nvr_system_info, get_people_attach_sample
import httpx

router = APIRouter(prefix="/api", tags=["people-counting"])


@router.get("/presence", response_model=PresenceResponse)
async def get_presence() -> PresenceResponse:
    snapshot = people_service.get_presence_snapshot()
    return PresenceResponse(
        timestamp=snapshot["timestamp"],
        presenti_totali=snapshot["presenti_totali"],
        per_camera=[CameraPresence(**c) for c in snapshot["per_camera"]],
        since_reset=snapshot["since_reset"],
    )


@router.get("/nvr-info")
async def nvr_info():
    """
    Endpoint di test: verifica connessione + autenticazione verso l'NVR
    e restituisce le info di sistema grezze.
    """
    try:
        info = await get_nvr_system_info()
        return info
    except httpx.HTTPStatusError as exc:
        # Se le credenziali sono sbagliate o l'NVR risponde con errore
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"NVR HTTP error: {exc}",
        )
    except Exception as exc:  # pragma: no cover - diagnostico
        raise HTTPException(status_code=500, detail=f"NVR connection error: {exc}")


@router.get("/debug/state")
async def debug_state():
    """
    Restituisce lo stato interno per canale:
    - api_channel
    - last_entered / last_exited
    - occupancy calcolato
    Così puoi confrontare direttamente con i contatori mostrati nella GUI Dahua.
    """
    return {"channels": people_service.get_debug_state()}


@router.get("/debug/attach-sample")
async def debug_attach_sample(
    channel: int = Query(..., description="Numero di canale da sondare (es. 4 o 6)")
):
    """
    Apre per pochi istanti lo stream attach del canale indicato e restituisce
    i primi byte ricevuti, così possiamo vedere il formato reale degli eventi.
    """
    try:
        sample = await get_people_attach_sample(channel)
        return sample
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"NVR HTTP error: {exc}",
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"NVR attach error: {exc}")




