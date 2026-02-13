"""Sincronizzazione periodica dei contatori dalla telecamera via getSummary."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _parse_key_value(text: str) -> dict[str, str]:
    """Parsifica risposta key=valore da getSummary."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _extract_from_fields(fields: dict[str, str]) -> dict[str, Any] | None:
    """Estrae entered ed exited dai campi parsati (solo ingressi/uscite)."""
    entered = fields.get("summary.EnteredSubtotal.Today") or fields.get(
        "summary.EnteredSubtotal.Total"
    )
    exited = fields.get("summary.ExitedSubtotal.Today") or fields.get(
        "summary.ExitedSubtotal.Total"
    )
    if entered is None or exited is None:
        return None
    try:
        return {
            "entered": int(entered),
            "exited": int(exited),
        }
    except ValueError:
        return None


async def fetch_camera_summary(
    host: str,
    port: int,
    username: str,
    password: str,
    channel: int = 1,
    rule_name: str = "Presenti-Reception",
    camera_label: str = "",
) -> dict[str, Any] | None:
    """
    Chiama getSummary sulla telecamera e restituisce EnteredSubtotal.Today,
    ExitedSubtotal.Today (solo ingressi/uscite, nessun inside).
    Se name=rule_name non restituisce dati, prova senza name (solo channel).
    Ritorna None in caso di errore.
    """
    url = f"http://{host}:{port}/cgi-bin/videoStatServer.cgi"
    auth = httpx.DigestAuth(username, password)
    label = camera_label or f"{host}:{port}"

    # Prova con name, poi senza (D6 potrebbe avere regola con nome diverso)
    params_list = [
        {"action": "getSummary", "channel": str(channel), "name": rule_name},
        {"action": "getSummary", "channel": str(channel)},
    ]

    for params in params_list:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, auth=auth)
                resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "getSummary %s params=%s failed: %s",
                label, params, exc,
            )
            continue

        fields = _parse_key_value(resp.text)
        result = _extract_from_fields(fields)
        if result:
            return result

        # Log per debug quando fallisce
        if not result and params.get("name"):
            logger.info(
                "getSummary %s (name=%s): Entered/Exited mancanti. Campi: %s",
                label, rule_name,
                list(fields.keys())[:20],
            )

    return None
