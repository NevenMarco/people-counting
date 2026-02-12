from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


PeopleTotalsHandler = Callable[[int, int, int], Awaitable[None]]
InsideTotalsHandler = Callable[[int, int], Awaitable[None]]


@dataclass
class DeviceSource:
    """
    Rappresenta una sorgente di dati people-count (camera IP o NVR).
    logical_channel è l'ID interno che useremo nel servizio (es. 3 per D4, 5 per D6),
    mentre attach_channel è il valore passato nell'URL ?channel=... del dispositivo.
    """

    name: str
    host: str
    port: int
    username: str
    password: str
    logical_channel: int
    attach_channel: int


class DahuaPeopleSubscriber:
    """
    Gestisce le connessioni 'attach' verso uno o più dispositivi Dahua.
    Per ogni blocco di testo ricevuto, estrae i totali people counting
    e chiama il callback handler.
    """

    def __init__(
        self,
        totals_handler: PeopleTotalsHandler,
        inside_handler: Optional[InsideTotalsHandler] = None,
    ) -> None:
        # Handler per NumberStat (Entered/Exited)
        self._totals_handler = totals_handler
        # Handler opzionale per ManNumDetection (InsideSubtotal.Total)
        self._inside_handler = inside_handler
        self._tasks: list[asyncio.Task] = []
        self._stopped = asyncio.Event()

    async def start(self, sources: list[DeviceSource]) -> None:
        self._stopped.clear()
        for src in sources:
            task = asyncio.create_task(
                self._run_source(src), name=f"attach-{src.name}"
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        self._stopped.set()
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    async def _run_source(self, src: DeviceSource) -> None:
        url = f"http://{src.host}:{src.port}/cgi-bin/videoStatServer.cgi"
        params = {"action": "attach", "channel": str(src.attach_channel), "heartbeat": "5"}

        # Digest auth client riutilizzabile
        auth = httpx.DigestAuth(src.username, src.password)

        backoff = 1
        max_backoff = 60

        while not self._stopped.is_set():
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    logger.info(
                        "Opening attach stream for device %s (%s:%s, attach_channel=%s, logical_channel=%s)",
                        src.name,
                        src.host,
                        src.port,
                        src.attach_channel,
                        src.logical_channel,
                    )
                    async with client.stream(
                        "GET", url, params=params, auth=auth
                    ) as response:
                        response.raise_for_status()
                        content_type = response.headers.get("Content-Type", "")
                        logger.debug("Attach response Content-Type: %s", content_type)

                        async for block in _iter_multipart_blocks(response):
                            if not block:
                                continue
                            text = block.strip()
                            # Heartbeat non contiene dati utili
                            if text == "Heartbeat":
                                continue

                            try:
                                fields = _parse_key_value_block(text)
                                rule_name = fields.get("summary.RuleName")

                                # Evento di tipo NumberStat: conteggio entrati/usciti (del giorno)
                                if rule_name == "NumberStat":
                                    entered_str = fields.get(
                                        "summary.EnteredSubtotal.Today"
                                    )
                                    exited_str = fields.get(
                                        "summary.ExitedSubtotal.Today"
                                    )
                                    if (
                                        entered_str is None
                                        or exited_str is None
                                        or self._totals_handler is None
                                    ):
                                        continue
                                    entered = int(entered_str)
                                    exited = int(exited_str)
                                    await self._totals_handler(
                                        src.logical_channel, entered, exited
                                    )

                                # Evento di tipo ManNumDetection: persone presenti in area
                                elif rule_name == "ManNumDetection":
                                    if self._inside_handler is None:
                                        continue
                                    inside_str = fields.get(
                                        "summary.InsideSubtotal.Total"
                                    )
                                    if inside_str is None:
                                        continue
                                    inside = int(inside_str)
                                    await self._inside_handler(
                                        src.logical_channel, inside
                                    )

                                # altri RuleName non ci interessano
                                else:
                                    continue
                            except Exception:
                                logger.warning(
                                    "Invalid people-count block on device %s (logical_channel=%s): %r",
                                    src.name,
                                    src.logical_channel,
                                    text,
                                )

                # Se usciamo dal contesto senza eccezioni, aspetta un po' e riconnetti
                backoff = 1

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Attach stream error on device %s (logical_channel=%s): %s. Reconnecting in %ss",
                    src.name,
                    src.logical_channel,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)


async def _iter_multipart_blocks(response: httpx.Response):
    """
    Lettore semplice per stream multipart/x-mixed-replace.
    Restituisce il body testuale di ciascun blocco.
    """
    boundary = None
    content_type = response.headers.get("Content-Type", "")
    if "boundary=" in content_type:
        boundary = content_type.split("boundary=")[-1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
    if boundary:
        boundary = ("--" + boundary).encode()

    buffer = b""
    async for chunk in response.aiter_bytes():
        buffer += chunk
        # Se conosciamo il boundary, tagliamo le parti
        if boundary and boundary in buffer:
            parts = buffer.split(boundary)
            # Mantieni l'ultima porzione come buffer parziale
            buffer = parts[-1]
            for raw in parts[:-1]:
                body = _extract_body(raw)
                if body:
                    yield body
        else:
            # Finché non conosciamo il boundary ci limitiamo ad accumulare
            # (nei tuoi log il Content-Type dichiara già un boundary).
            continue


def _extract_body(raw_part: bytes) -> str | None:
    """
    Estrae la parte di body testuale da un singolo pezzo multipart.
    Cerca separatore header/body vuota (\r\n\r\n).
    """
    if not raw_part.strip():
        return None
    try:
        header_body_split = raw_part.split(b"\r\n\r\n", 1)
        if len(header_body_split) != 2:
            return None
        body = header_body_split[1].strip()
        # Rimuovi eventuale terminatore --
        if body.endswith(b"--"):
            body = body[:-2]
        return body.decode(errors="ignore")
    except Exception:
        return None


def _parse_key_value_block(text: str) -> dict[str, str]:
    """
    Parsifica un blocco di testo in formato:
      chiave=valore
    con una coppia per riga. Restituisce un dizionario.
    Esempio:
      summary.EnteredSubtotal.Today=42
      summary.ExitedSubtotal.Today=38
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result

