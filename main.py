from fastapi import FastAPI, status
from src.shared.config import settings

app = FastAPI()

@app.get("/")
async def root() -> dict:
    return {"app_status": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> str:
    return "PONG"

