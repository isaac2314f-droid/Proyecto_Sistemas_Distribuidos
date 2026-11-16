import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import closing
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from inbox import DATABASE_PATH

CENTRAL_URL = os.getenv("CENTRAL_URL", "").rstrip("/")
logger = logging.getLogger("uvicorn.error")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = build_opener(NoRedirect())


def prepare_outbox(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS outbox (
            message_id TEXT PRIMARY KEY NOT NULL,
            lamport INTEGER NOT NULL,
            payload TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt REAL NOT NULL DEFAULT 0
        )
    """)


def enqueue_message(db, saved):
    if not CENTRAL_URL:
        return

    payload = {
        "id": saved["id"],
        "from": f'{saved["username"]}@{saved["origin"]}',
        "origin": saved["origin"],
        "lamport": saved["lamport"],
        "sent_at": saved["sent_at"],
        "body": saved["body"],
    }
    db.execute(
        "INSERT INTO outbox (message_id, lamport, payload) VALUES (?, ?, ?)",
        (payload["id"], payload["lamport"], json.dumps(payload)),
    )


def deliver_next():
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        job = db.execute("""
            SELECT message_id, lamport, payload, attempts
            FROM outbox
            WHERE next_attempt <= ?
            ORDER BY lamport, message_id
            LIMIT 1
        """, (time.time(),)).fetchone()

    if job is None:
        return False

    message_id, lamport, payload, attempts = job
    request = Request(
        f"{CENTRAL_URL}/messages",
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    retry = False
    try:
        with opener.open(request, timeout=3):
            pass
        logger.info("Mensaje enviado id=%s lamport=%s", message_id, lamport)
    except HTTPError as error:
        retry = 500 <= error.code < 600
        logger.warning(
            "Central respondió HTTP %s id=%s lamport=%s",
            error.code, message_id, lamport,
        )
        error.close()
    except (OSError, ValueError) as error:
        retry = True
        logger.warning(
            "Central sin respuesta id=%s lamport=%s: %s",
            message_id, lamport, error,
        )

    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        if retry:
            delay = min(60, 2 ** min(attempts + 1, 6))
            db.execute("""
                UPDATE outbox
                SET attempts = attempts + 1, next_attempt = ?
                WHERE message_id = ?
            """, (time.time() + delay, message_id))
            logger.info("Reintento en %ss id=%s lamport=%s", delay, message_id, lamport)
        else:
            db.execute("DELETE FROM outbox WHERE message_id = ?", (message_id,))

        db.commit()

    return True


async def send_pending(registered):
    if not CENTRAL_URL:
        return

    while True:
        await registered.wait()
        if not await asyncio.to_thread(deliver_next):
            await asyncio.sleep(1)