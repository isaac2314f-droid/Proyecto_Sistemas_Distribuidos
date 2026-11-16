import os
import sqlite3
from contextlib import asynccontextmanager, closing

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