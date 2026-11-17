import asyncio
import json
import logging
import os
from urllib.request import Request, urlopen
import sqlite3

from history import recover_history

logger = logging.getLogger("uvicorn.error")


def register_once(central_url, group_name, public_url):
    with urlopen(f"{central_url}/health", timeout=3):
        pass

    payload = json.dumps({"server": group_name, "url": public_url}).encode()
    request = Request(
        f"{central_url}/register",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3):
        pass


async def renew_registration(registered):
    central_url = os.getenv("CENTRAL_URL", "").rstrip("/")
    group_name = os.getenv("GROUP_NAME", "")
    public_url = os.getenv("PUBLIC_URL", "")

    if not all((central_url, group_name, public_url)):
        logger.info("Registro central pendiente de configuración.")
        return

    history_pending = True

    while True:
        try:
            await asyncio.to_thread(register_once, central_url, group_name, public_url)
        except (OSError, ValueError) as error:
            registered.clear()
            history_pending = True
            logger.warning("Registro central de %s pendiente: %s", group_name, error)
        else:
            registered.set()
            logger.info("Registro central confirmado para %s", group_name)

            if history_pending:
                try:
                    count = await asyncio.to_thread(recover_history, central_url)
                except (OSError, ValueError, sqlite3.Error) as error:
                    logger.warning("Recuperación de historial pendiente: %s", error)
                else:
                    history_pending = False
                    logger.info("Historial consultado: %s mensajes", count)

        await asyncio.sleep(10)