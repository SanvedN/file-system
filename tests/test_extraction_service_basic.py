from starlette.testclient import TestClient


def test_extraction_service_ping(extraction_app):
    client = TestClient(extraction_app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.text == '"PONG"'


def test_extraction_service_root(extraction_app):
    client = TestClient(extraction_app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["extraction_service"] == "Running"

