from fastapi import FastAPI, status
from src.shared.config import Settings

app = FastAPI()

settings = Settings()


@app.get("/")
async def root() -> dict:
    return {"app_status": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def get_health() -> str:
    return "PONG"
