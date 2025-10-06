from fastapi import Depends, FastAPI, status
from shared.db import get_db
from shared.cache import get_redis
import extraction_service.routes as extraction_routes

app = FastAPI()


@app.get("/")
async def root() -> dict:
    return {"extraction_service": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> str:
    return "PONG"


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


app.include_router(
    extraction_routes.router,
    dependencies=[Depends(get_db), Depends(get_redis)],
    tags=["Embeddings"],
)
