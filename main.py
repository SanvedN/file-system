from fastapi import FastAPI, status
from src.shared.config import Settings

app = FastAPI()

settings = Settings()


@app.get("/")
async def root() -> dict:
    return {"app_status": "Running"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def get_health() -> dict:
    return {"status": "OK"}


@app.get("/get_base_path")
async def get_base_path() -> dict:
    return {"base_path": settings.base_path}
