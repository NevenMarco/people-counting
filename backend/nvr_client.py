from __future__ import annotations

import httpx

from .config import get_settings


async def get_nvr_system_info() -> dict:
    """
    Prova di connessione/autenticazione verso l'NVR.
    Usa un endpoint di sistema (magicBox) e restituisce
    il testo grezzo più alcuni metadati.
    """
    settings = get_settings()
    url = f"http://{settings.nvr_host}:{settings.nvr_port}/cgi-bin/magicBox.cgi"
    params = {"action": "getSystemInfo"}
    auth = httpx.DigestAuth(settings.nvr_username, settings.nvr_password)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, auth=auth, timeout=10.0)
        resp.raise_for_status()

    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": resp.text,
    }


async def get_people_attach_sample(channel: int, max_bytes: int = 4096) -> dict:
    """
    Apre temporaneamente lo stream 'attach' per un canale e restituisce
    un dump grezzo dei primi byte ricevuti. Serve per capire il formato
    reale degli eventi people counting e i nomi dei campi.
    """
    settings = get_settings()
    url = f"http://{settings.nvr_host}:{settings.nvr_port}/cgi-bin/videoStatServer.cgi"
    params = {"action": "attach", "channel": str(channel), "heartbeat": "5"}
    auth = httpx.DigestAuth(settings.nvr_username, settings.nvr_password)

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, params=params, auth=auth) as resp:
            resp.raise_for_status()
            collected = b""
            async for chunk in resp.aiter_bytes():
                collected += chunk
                if len(collected) >= max_bytes:
                    break

    text = collected.decode(errors="ignore")
    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "raw_sample": text,
    }


