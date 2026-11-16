import asyncio
import sqlite3
from contextlib import asynccontextmanager, closing, suppress
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from federation import renew_registration
from inbox import DATABASE_PATH, GROUP_NAME, advance_clock, prepare_inbox, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY NOT NULL,
                username TEXT NOT NULL,
                body TEXT NOT NULL,
                sent_at TEXT NOT NULL
            )
        """)
        prepare_inbox(db)
        db.commit()

    registration_task = asyncio.create_task(renew_registration())
    try:
        yield
    finally:
        registration_task.cancel()
        with suppress(asyncio.CancelledError):
            await registration_task


app = FastAPI(title="Chat distribuido", lifespan=lifespan)
app.include_router(router)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")


class MessageCreate(UserCreate):
    body: str = Field(min_length=1, max_length=500)


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(Path(__file__).with_name("index.html"), media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/users", status_code=201)
def create_user(user: UserCreate):
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        result = db.execute(
            "INSERT INTO users (username) VALUES (?) ON CONFLICT(username) DO NOTHING",
            (user.username,),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="El usuario ya existe")
        db.commit()

    return {"username": user.username}


@app.post("/messages", status_code=201)
def create_message(message: MessageCreate):
    body = message.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Escribe un mensaje")

    saved = {
        "id": str(uuid4()),
        "username": message.username,
        "body": body,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "origin": GROUP_NAME,
    }

    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        user = db.execute(
            "SELECT username FROM users WHERE username = ?",
            (message.username,),
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="El usuario no existe")

        db.execute("BEGIN IMMEDIATE")
        saved["lamport"] = advance_clock(db)
        db.execute("""
            INSERT INTO messages (id, username, body, sent_at, origin, lamport)
            VALUES (:id, :username, :body, :sent_at, :origin, :lamport)
        """, saved)
        db.commit()

    return saved


@app.get("/messages")
def list_messages():
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        db.row_factory = sqlite3.Row
        messages = db.execute("""
            SELECT id, username, body, sent_at, origin, lamport
            FROM messages
            ORDER BY lamport, origin, id
        """).fetchall()

    return [dict(message) for message in messages]