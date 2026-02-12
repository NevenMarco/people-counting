"""Servizio per caricare/salvare impostazioni admin dal DB."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import AdminSettings

SETTINGS_KEYS = [
    "admin_password",  # password admin (override env se impostata)
    "camera_d4_host",
    "camera_d4_port",
    "camera_d4_username",
    "camera_d4_password",
    "camera_d6_host",
    "camera_d6_port",
    "camera_d6_username",
    "camera_d6_password",
    "rule_area_name",  # es. PC-1
]


def get_effective_admin_password(db_settings: dict[str, Any] | None) -> str:
    """Password admin: da DB se impostata, altrimenti da env."""
    if db_settings and db_settings.get("admin_password"):
        return str(db_settings["admin_password"])
    return get_settings().admin_password


async def load_admin_settings(session: AsyncSession) -> dict[str, Any]:
    """Carica le impostazioni dal DB. Ritorna un dict con i valori (stringa o int)."""
    rows = (await session.scalars(select(AdminSettings))).all()
    result: dict[str, Any] = {}
    for row in rows:
        if row.key in ("camera_d4_port", "camera_d6_port"):
            try:
                result[row.key] = int(row.value)
            except ValueError:
                result[row.key] = 80
        else:
            result[row.key] = row.value
    return result


async def save_admin_settings(session: AsyncSession, data: dict[str, Any]) -> None:
    """Salva le impostazioni nel DB."""
    for key in SETTINGS_KEYS:
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, int):
            val = str(val)
        row = await session.get(AdminSettings, key)
        if row:
            row.value = val
        else:
            session.add(AdminSettings(key=key, value=val))


def get_effective_camera_config(session_result: dict[str, Any] | None) -> dict[str, Any]:
    """
    Restituisce la config effettiva: valori dal DB se presenti, altrimenti da env.
    session_result: output di load_admin_settings, o None se non ancora caricato.
    """
    env = get_settings()
    out = {
        "camera_d4_host": env.camera_d4_host,
        "camera_d4_port": env.camera_d4_port,
        "camera_d4_username": env.camera_d4_username,
        "camera_d4_password": env.camera_d4_password,
        "camera_d4_channel": env.camera_d4_channel,
        "camera_d4_attach_channel": env.camera_d4_attach_channel,
        "camera_d6_host": env.camera_d6_host,
        "camera_d6_port": env.camera_d6_port,
        "camera_d6_username": env.camera_d6_username,
        "camera_d6_password": env.camera_d6_password,
        "camera_d6_channel": env.camera_d6_channel,
        "camera_d6_attach_channel": env.camera_d6_attach_channel,
        "rule_area_name": "PC-1",
    }
    if session_result:
        for k, v in session_result.items():
            if k in out and v is not None:
                out[k] = v
    return out
