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


async def fetch_camera_summary(
    host: str,
    port: int,
    username: str,
    password: str,
    channel: int = 1,
    rule_name: str = "Presenti-Reception",
) -> dict[str, Any] | None:
    """
    Chiama getSummary sulla telecamera e restituisce EnteredSubtotal.Today,
    ExitedSubtotal.Today, InsideSubtotal.Total.
    Ritorna None in caso di errore.
    """
    url = f"http://{host}:{port}/cgi-bin/videoStatServer.cgi"
    params = {
        "action": "getSummary",
        "channel": str(channel),
        "name": rule_name,
    }
    auth = httpx.DigestAuth(username, password)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, auth=auth)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("getSummary %s:%s failed: %s", host, port, exc)
        return None

    fields = _parse_key_value(resp.text)

    # Preferiamo .Today, fallback su .Total
    entered = fields.get("summary.EnteredSubtotal.Today") or fields.get(
        "summary.EnteredSubtotal.Total"
    )
    exited = fields.get("summary.ExitedSubtotal.Today") or fields.get(
        "summary.ExitedSubtotal.Total"
    )
    inside = fields.get("summary.InsideSubtotal.Total")

    if entered is None or exited is None:
        logger.debug(
            "getSummary %s:%s: Entered/Exited mancanti, campi: %s",
            host, port,
            [k for k in fields if "Entered" in k or "Exited" in k],
        )
        return None

    try:
        return {
            "entered": int(entered),
            "exited": int(exited),
            "inside": int(inside) if inside is not None else None,
        }
    except ValueError:
        return None
