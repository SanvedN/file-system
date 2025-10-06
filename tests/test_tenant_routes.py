import types
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def tenant_router_app():
    from src.file_service.app import app
    return app


def test_tenant_ping(tenant_router_app):
    client = TestClient(tenant_router_app)
    r = client.get("/v2/tenants/ping")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_get_update_delete_tenant(monkeypatch, tenant_router_app):
    from src.file_service.services import tenant_service as svc

    async def fake_create(db, redis, payload):
        return types.SimpleNamespace(
            tenant_id="00000000-0000-0000-0000-000000000001",
            tenant_code=payload.tenant_code,
            configuration=(payload.configuration.dict() if payload.configuration else {}),
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

    async def fake_get(db, redis, code):
        return types.SimpleNamespace(
            tenant_id="00000000-0000-0000-0000-000000000001",
            tenant_code=code,
            configuration={},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

    async def fake_update(db, redis, code, payload):
        return await fake_get(db, redis, code)

    async def fake_delete(db, redis, code, background=None):
        return {"deleted": True}

    monkeypatch.setattr(svc, "create_tenant", fake_create)
    monkeypatch.setattr(svc, "get_tenant_by_code", fake_get)
    monkeypatch.setattr(svc, "update_tenant", fake_update)
    monkeypatch.setattr(svc, "delete_tenant", fake_delete)

    client = TestClient(tenant_router_app)

    # create
    r = client.post("/v2/tenants/", json={"tenant_code": "ACME"})
    assert r.status_code == 201
    body = r.json()
    assert body["tenant_code"] == "ACME"

    # get
    r = client.get("/v2/tenants/ACME")
    assert r.status_code == 200
    assert r.json()["tenant_code"] == "ACME"

    # patch
    r = client.patch("/v2/tenants/ACME", json={"configuration": {"max_file_size_kbytes": 1024}})
    assert r.status_code == 200

    # delete
    r = client.delete("/v2/tenants/ACME")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


