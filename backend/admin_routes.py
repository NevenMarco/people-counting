"""Route admin protette da password."""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .admin_settings import get_effective_admin_password, load_admin_settings, save_admin_settings
from .config import get_settings
from .db import get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Token in memoria (in produzione usare Redis o DB)
_admin_tokens: set[str] = set()


def _verify_admin(request: Request) -> str | None:
    """Restituisce il token se presente e valido nel cookie."""
    token = request.cookies.get("admin_token")
    if token and token in _admin_tokens:
        return token
    return None


class LoginRequest(BaseModel):
    password: str


class AdminSettingsSchema(BaseModel):
    camera_d4_host: str = ""
    camera_d4_port: int = 80
    camera_d4_username: str = ""
    camera_d4_password: str = ""
    camera_d6_host: str = ""
    camera_d6_port: int = 80
    camera_d6_username: str = ""
    camera_d6_password: str = ""
    rule_area_name: str = "Presenti-Reception"


@router.post("/login")
async def admin_login(req: LoginRequest, response: Response):
    """Verifica password e imposta cookie di sessione."""
    async with get_session() as session:
        db_data = await load_admin_settings(session)
    effective_password = get_effective_admin_password(db_data)
    if req.password != effective_password:
        raise HTTPException(status_code=401, detail="Password errata")
    token = secrets.token_urlsafe(32)
    _admin_tokens.add(token)
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return {"status": "ok"}


@router.post("/logout")
async def admin_logout(request: Request, response: Response):
    """Rimuove la sessione admin."""
    token = request.cookies.get("admin_token")
    if token:
        _admin_tokens.discard(token)
    response.delete_cookie("admin_token")
    return {"status": "ok"}


@router.get("/check")
async def admin_check(request: Request):
    """Verifica se la sessione admin è valida."""
    if _verify_admin(request):
        return {"authenticated": True}
    return {"authenticated": False}


@router.get("/settings", response_model=AdminSettingsSchema)
async def get_admin_settings(request: Request):
    """Restituisce le impostazioni (solo se autenticato)."""
    if not _verify_admin(request):
        raise HTTPException(status_code=401, detail="Autenticazione richiesta")

    async with get_session() as session:
        data = await load_admin_settings(session)

    env = get_settings()
    return AdminSettingsSchema(
        camera_d4_host=data.get("camera_d4_host") or env.camera_d4_host,
        camera_d4_port=int(data.get("camera_d4_port") or env.camera_d4_port),
        camera_d4_username=data.get("camera_d4_username") or env.camera_d4_username,
        camera_d4_password=data.get("camera_d4_password") or env.camera_d4_password,
        camera_d6_host=data.get("camera_d6_host") or env.camera_d6_host,
        camera_d6_port=int(data.get("camera_d6_port") or env.camera_d6_port),
        camera_d6_username=data.get("camera_d6_username") or env.camera_d6_username,
        camera_d6_password=data.get("camera_d6_password") or env.camera_d6_password,
        rule_area_name=data.get("rule_area_name") or "Presenti-Reception",
    )


@router.put("/settings")
async def put_admin_settings(request: Request, body: AdminSettingsSchema):
    """Salva le impostazioni (solo se autenticato)."""
    if not _verify_admin(request):
        raise HTTPException(status_code=401, detail="Autenticazione richiesta")

    async with get_session() as session:
        data = body.model_dump()
        await save_admin_settings(session, data)

    return {"status": "ok", "message": "Impostazioni salvate. Riavvia il backend per applicare."}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/password")
async def change_admin_password(request: Request, body: ChangePasswordRequest):
    """Cambia la password admin (solo se autenticato)."""
    if not _verify_admin(request):
        raise HTTPException(status_code=401, detail="Autenticazione richiesta")

    async with get_session() as session:
        db_data = await load_admin_settings(session)
    effective_password = get_effective_admin_password(db_data)

    if body.current_password != effective_password:
        raise HTTPException(status_code=400, detail="Password attuale errata")

    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="La nuova password deve avere almeno 6 caratteri")

    async with get_session() as session:
        await save_admin_settings(session, {"admin_password": body.new_password})

    return {"status": "ok", "message": "Password aggiornata."}


@router.post("/restart")
async def restart_backend(request: Request):
    """Riavvia il container Docker del backend (solo se autenticato)."""
    if not _verify_admin(request):
        raise HTTPException(status_code=401, detail="Autenticazione richiesta")

    try:
        import docker
        client = docker.from_env()
        # Il container name è people-counting-backend (da docker-compose)
        container_name = os.environ.get("CONTAINER_NAME", "people-counting-backend")
        container = client.containers.get(container_name)
        container.restart()
        return {"status": "ok", "message": "Riavvio in corso..."}
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Riavvio non disponibile: installare docker e montare /var/run/docker.sock",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore riavvio: {str(e)}")
