import types
import pytest
import httpx


@pytest.mark.anyio
async def test_file_list_route(monkeypatch, file_app):
    # monkeypatch service list_files
    from src.file_service.services import file_service as svc

    async def fake_list(db, tenant_id, redis=None):
        return [
            {"file_id": "F1", "file_name": "a.txt", "media_type": "text/plain", "file_size_bytes": 1, "tag": None, "file_metadata": None, "created_at": None, "modified_at": None}
        ]

    monkeypatch.setattr(svc, "list_files", fake_list)

    transport = httpx.ASGITransport(app=file_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/v2/tenants/00000000-0000-0000-0000-000000000001/files")
    assert r.status_code == 200
    assert r.json()["files"][0]["file_id"] == "F1"


@pytest.mark.anyio
async def test_file_get_route(monkeypatch, file_app):
    from src.file_service.services import file_service as svc
    class Obj:
        file_id="F1"; file_name="a.txt"; media_type="text/plain"; file_size_bytes=1; tag=None; file_metadata=None; created_at=None; modified_at=None
    async def fake_get(db, tenant_id, file_id, redis=None):
        return Obj()
    monkeypatch.setattr(svc, "get_file", fake_get)

    transport = httpx.ASGITransport(app=file_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/v2/tenants/00000000-0000-0000-0000-000000000001/files/F1")
    assert r.status_code == 200
    assert r.json()["file_id"] == "F1"


@pytest.mark.anyio
async def test_file_search_route(monkeypatch, file_app):
    from src.file_service.services import file_service as svc
    async def fake_search(db, tenant_id, filters, sort_field, sort_order, page, limit):
        class X:
            file_id="F1"; file_name="a.txt"; media_type="text/plain"; file_size_bytes=1; tag=None; file_metadata=None; created_at=None; modified_at=None
        return [X()], 1
    monkeypatch.setattr(svc, "search_files", fake_search)

    transport = httpx.ASGITransport(app=file_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = {"filters": {}, "sort": {"field": "created_at", "order": "desc"}, "pagination": {"page": 1, "limit": 50}}
        r = await client.post("/v2/tenants/00000000-0000-0000-0000-000000000001/files/search", json=body)
    assert r.status_code == 200
    assert r.json()["files"][0]["file_id"] == "F1"

