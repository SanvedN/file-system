import pytest
from starlette.testclient import TestClient


def test_gateway_root(gateway_app):
    client = TestClient(gateway_app)
    r = client.get("/")
    assert r.status_code == 200
    json_data = r.json()
    assert "gateway" in json_data, f"Unexpected response: {json_data}"
    assert json_data["gateway"] == "Running"



def test_gateway_ping(gateway_app):
    client = TestClient(gateway_app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.text == '"PONG"'


def test_gateway_health(gateway_app, mock_gateway_http):
    client = TestClient(gateway_app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("up", "degraded")


def test_gateway_route_to_file(gateway_app, mock_gateway_http):
    client = TestClient(gateway_app)
    r = client.get("/v2/tenants/123/files")
    assert r.status_code == 200
    assert r.json()["service"] == "file"


def test_gateway_route_to_extraction(gateway_app, mock_gateway_http):
    client = TestClient(gateway_app)
    r = client.get("/v2/tenants/123/embeddings/abc")
    assert r.status_code == 200
    assert r.json()["service"] == "extraction"


