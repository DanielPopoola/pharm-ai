from fastapi import FastAPI

from app.core.logging import setup_logging

setup_logging()

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}
