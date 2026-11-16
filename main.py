import os
import sqlite3
from contextlib import asynccontextmanager, closing

from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
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
        db.commit()
    yield


app = FastAPI(title="Chat distribuido", lifespan=lifespan)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")


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
class MessageCreate(UserCreate):
    body: str = Field(min_length=1, max_length=500)


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
    }

    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        user = db.execute(
            "SELECT username FROM users WHERE username = ?",
            (message.username,),
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="El usuario no existe")

        db.execute("""
            INSERT INTO messages (id, username, body, sent_at)
            VALUES (:id, :username, :body, :sent_at)
        """, saved)
        db.commit()

    return saved


@app.get("/messages")
def list_messages():
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        db.row_factory = sqlite3.Row
        messages = db.execute("""
            SELECT id, username, body, sent_at
            FROM messages
            ORDER BY sent_at, id
        """).fetchall()

    return [dict(message) for message in messages]