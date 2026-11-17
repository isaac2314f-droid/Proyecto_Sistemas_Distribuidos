import logging

from inbox import FederatedMessage
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Central simulado")
logger = logging.getLogger("uvicorn.error")
registered = {}


class Registration(BaseModel):
    server: str
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(registration: Registration):
    registered[registration.server] = registration.url
    logger.info("Registrado %s en %s", registration.server, registration.url)
    return {"status": "ok"}

received = {}


@app.post("/messages")
def accept_message(message: FederatedMessage):
    message_id = str(message.id)
    received.setdefault(message_id, message)
    logger.info("Central recibió id=%s lamport=%s", message_id, message.lamport)
    return {"status": "ok"}

@app.get("/history")
def get_history(since: int = 0):
    messages = [
        message
        for message in received.copy().values()
        if message.lamport > since
    ]
    messages.sort(key=lambda message: (message.lamport, message.origin, str(message.id)))
    return [message.model_dump(mode="json", by_alias=True) for message in messages]