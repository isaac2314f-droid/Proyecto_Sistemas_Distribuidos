from fastapi import FastAPI

app = FastAPI(title="Chat distribuido")


@app.get("/health")
def health():
    return {"status": "ok"}