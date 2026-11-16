import logging

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