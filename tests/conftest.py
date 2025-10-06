import asyncio
import types
import pytest
import httpx
from fastapi import FastAPI


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def gateway_app():
    from app import app as gateway
    return gateway


async def _dummy_gen():
    class Dummy:
        pass
    yield Dummy()


@pytest.fixture
def file_app(monkeypatch):
    from src.file_service.app import app as file_app
    # Override global router dependencies to avoid real DB/Redis
    from src.shared.db import get_db
    from src.shared.cache import get_redis
    file_app.dependency_overrides[get_db] = _dummy_gen
    file_app.dependency_overrides[get_redis] = _dummy_gen
    return file_app


@pytest.fixture
def extraction_app(monkeypatch):
    from src.extraction_service.app import app as ext_app
    from src.shared.db import get_db
    from src.shared.cache import get_redis
    ext_app.dependency_overrides[get_db] = _dummy_gen
    ext_app.dependency_overrides[get_redis] = _dummy_gen
    return ext_app


class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, *args, **kwargs):
        # Health checks synthetic
        if url.endswith("/ping"):
            return httpx.Response(200, content=b"PONG")
        return httpx.Response(200, json={"ok": True})

    async def request(self, method, url, content=None, headers=None):
        # Route based response flag
        body = {}
        if "/embeddings" in url:
            body = {"service": "extraction"}
        else:
            body = {"service": "file"}
        return httpx.Response(200, json=body)


@pytest.fixture
def mock_gateway_http(monkeypatch):
    import app as gateway_module
    monkeypatch.setattr(gateway_module, "httpx", types.SimpleNamespace(AsyncClient=DummyAsyncClient))
    yield

