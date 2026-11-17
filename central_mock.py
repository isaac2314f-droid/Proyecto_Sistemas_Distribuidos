import logging
from threading import Lock
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from inbox import FederatedMessage

app = FastAPI(title="Central simulado")
logger = logging.getLogger("uvicorn.error")

registered: dict[str, str] = {}
received: dict[str, FederatedMessage] = {}
state_lock = Lock()


class Registration(BaseModel):
    server: str
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(registration: Registration):
    with state_lock:
        registered[registration.server] = registration.url

    logger.info("Registrado %s en %s", registration.server, registration.url)
    return {"status": "ok"}


def forward_message(group, address, message):
    request = Request(
        f"{address.rstrip('/')}/fed/messages",
        data=message.model_dump_json(by_alias=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=3):
            pass

        logger.info(
            "Reenviado a %s id=%s lamport=%s",
            group, message.id, message.lamport,
        )
    except (OSError, ValueError) as error:
        logger.warning(
            "Reenvío a %s falló id=%s lamport=%s: %s",
            group, message.id, message.lamport, error,
        )


@app.post("/messages")
def accept_message(message: FederatedMessage, background_tasks: BackgroundTasks):
    message_id = str(message.id)

    with state_lock:
        if message_id in received:
            return {"status": "ok"}

        received[message_id] = message
        destinations = [
            (group, address)
            for group, address in registered.items()
            if group != message.origin
        ]

    logger.info("Central recibió id=%s lamport=%s", message_id, message.lamport)

    for group, address in destinations:
        background_tasks.add_task(forward_message, group, address, message)

    return {"status": "ok"}


@app.get("/history")
def get_history(since: int = 0):
    with state_lock:
        messages = [
            message
            for message in received.values()
            if message.lamport > since
        ]

    messages.sort(key=lambda message: (message.lamport, message.origin, str(message.id)))
    return [message.model_dump(mode="json", by_alias=True) for message in messages]