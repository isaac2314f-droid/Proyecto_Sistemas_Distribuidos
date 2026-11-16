import logging
import os
import sqlite3
from contextlib import closing
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat.db")
GROUP_NAME = os.getenv("GROUP_NAME") or "local"
router = APIRouter(prefix="/fed")
logger = logging.getLogger("uvicorn.error")


def prepare_inbox(db):
    columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}

    if "origin" not in columns:
        db.execute("ALTER TABLE messages ADD COLUMN origin TEXT NOT NULL DEFAULT ''")

    if "lamport" not in columns:
        db.execute("ALTER TABLE messages ADD COLUMN lamport INTEGER NOT NULL DEFAULT 0")

    db.execute("""
        CREATE TABLE IF NOT EXISTS chat_clock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            value INTEGER NOT NULL
        )
    """)
    db.execute("INSERT OR IGNORE INTO chat_clock (id, value) VALUES (1, 0)")


def advance_clock(db, received=0):
    current = db.execute("SELECT value FROM chat_clock WHERE id = 1").fetchone()[0]
    value = max(current, received) + 1
    db.execute("UPDATE chat_clock SET value = ? WHERE id = 1", (value,))
    return value


class FederatedMessage(BaseModel):
    id: UUID
    sender: str = Field(alias="from")
    origin: str
    lamport: int = Field(ge=0, lt=2**63 - 1)
    sent_at: str
    body: str


@router.get("/health")
def federation_health():
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        clock = db.execute("SELECT value FROM chat_clock WHERE id = 1").fetchone()[0]
    return {"server": GROUP_NAME, "lamport": clock}


@router.post("/messages")
def receive_message(message: FederatedMessage):
    message_id = str(message.id)

    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        result = db.execute("""
            INSERT INTO messages (id, username, body, sent_at, origin, lamport)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
        """, (
            message_id, message.sender, message.body, message.sent_at,
            message.origin, message.lamport,
        ))

        if result.rowcount == 0:
            logger.info("Duplicado descartado id=%s lamport=%s", message_id, message.lamport)
            return {"status": "ok"}

        advance_clock(db, message.lamport)
        db.commit()

    logger.info("Mensaje recibido id=%s lamport=%s", message_id, message.lamport)
    return {"status": "ok"}