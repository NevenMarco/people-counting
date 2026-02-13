from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .admin_settings import get_effective_camera_config, load_admin_settings
from .camera_sync import fetch_camera_summary
from .db import get_session
from .schemas import PresenceResponse, CameraPresence, SetOccupancyRequest
from .services import people_service
from .nvr_client import get_nvr_system_info, get_people_attach_sample
import httpx

router = APIRouter(prefix="/api", tags=["people-counting"])


@router.post("/reset")
async def reset_occupancy():
    """
    Resetta manualmente i contatori di occupazione a 0.
    """
    async with get_session() as session:
        await people_service.reset_occupancy(session, reason="MANUAL_RESET")
    return {"status": "ok", "message": "Occupancy reset to 0"}


@router.post("/set-occupancy")
async def set_occupancy(req: SetOccupancyRequest):
    """
    Imposta manualmente il numero totale di presenti.
    """
    async with get_session() as session:
        await people_service.set_occupancy(
            session, target_occupancy=req.occupancy, reason="MANUAL_SET"
        )
    return {"status": "ok", "message": f"Occupancy set to {req.occupancy}"}


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


@router.get("/debug/camera-compare")
async def debug_camera_compare():
    """
    Confronta last_entered/last_exited del server con i valori
    EnteredSubtotal.Today e ExitedSubtotal.Today letti via getSummary dalle telecamere.
    Utile per verificare che lo stato sia allineato.
    """
    async with get_session() as session:
        db_settings = await load_admin_settings(session)
    cfg = get_effective_camera_config(db_settings)
    rule_name = cfg.get("rule_area_name", "Presenti-Reception")

    our_state = people_service.get_debug_state()
    by_channel = {c["api_channel"]: c for c in our_state}

    result = []

    for name, ch_key, host, port, user, pwd, attach_ch in [
        ("D4", "camera_d4_channel", "camera_d4_host", "camera_d4_port",
         "camera_d4_username", "camera_d4_password", "camera_d4_attach_channel"),
        ("D6", "camera_d6_channel", "camera_d6_host", "camera_d6_port",
         "camera_d6_username", "camera_d6_password", "camera_d6_attach_channel"),
    ]:
        data = await fetch_camera_summary(
            host=cfg[host],
            port=cfg[port],
            username=cfg[user],
            password=cfg[pwd],
            channel=cfg[attach_ch],
            rule_name=rule_name,
        )
        api_ch = cfg[ch_key]
        our = by_channel.get(api_ch, {})

        result.append({
            "camera": name,
            "api_channel": api_ch,
            "camera_entered_today": data["entered"] if data else None,
            "camera_exited_today": data["exited"] if data else None,
            "camera_inside_total": data.get("inside") if data else None,
            "our_last_entered": our.get("last_entered"),
            "our_last_exited": our.get("last_exited"),
            "our_inside_total": our.get("inside_total"),
            "match": (
                data and our.get("last_entered") == data["entered"]
                and our.get("last_exited") == data["exited"]
            ) if data else None,
        })

    return {"rule_name": rule_name, "comparison": result}


@router.get("/debug/attach-sample")
async def debug_attach_sample(
    channel: int = Query(..., description="Numero di canale da sondare (es. 4 o 6)"),
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
