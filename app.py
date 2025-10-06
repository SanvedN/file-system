from __future__ import annotations

import asyncio
import os
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse
import httpx

FILE_SERVICE_BASE = os.getenv("FILE_SERVICE_BASE", "http://127.0.0.1:8001")
EXTRACTION_SERVICE_BASE = os.getenv("EXTRACTION_SERVICE_BASE", "http://127.0.0.1:8002")


app = FastAPI(title="API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {"main_app": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> str:
    return "PONG"


@app.get("/health")
async def health() -> JSONResponse:
    async with httpx.AsyncClient(timeout=3.0) as client:
        results = await asyncio.gather(
            client.get(f"{FILE_SERVICE_BASE}/ping"),
            client.get(f"{EXTRACTION_SERVICE_BASE}/ping"),
            return_exceptions=True,
        )
    statuses = []
    for svc, res in ("file_service", results[0]), ("extraction_service", results[1]):
        if isinstance(res, Exception):
            statuses.append({"service": svc, "status": "down"})
        else:
            statuses.append({"service": svc, "status": "up" if res.status_code == 200 else "degraded"})
    overall = "up" if all(s["status"] == "up" for s in statuses) else "degraded"
    return JSONResponse({"status": overall, "services": statuses})


def _route_base(path: str) -> str:
    if "/embeddings" in path:
        return EXTRACTION_SERVICE_BASE
    return FILE_SERVICE_BASE


async def _proxy(request: Request) -> Response:
    target_base = _route_base(request.url.path)
    target_url = f"{target_base}{request.url.path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=None) as client:
        body = await request.body()
        upstream = await client.request(
            request.method,
            target_url,
            content=body,
            headers=headers,
        )

    if upstream.headers.get("content-type", "").startswith("application/octet-stream") or "attachment" in upstream.headers.get("content-disposition", ""):
        return StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code, headers=dict(upstream.headers))

    return Response(content=upstream.content, status_code=upstream.status_code, headers=dict(upstream.headers))


@app.api_route("/v2/tenants/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_v2(full_path: str, request: Request):
    return await _proxy(request)


@app.api_route("/v1/tenants/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_v1(full_path: str, request: Request):
    return await _proxy(request)
