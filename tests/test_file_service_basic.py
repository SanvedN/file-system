from starlette.testclient import TestClient


def test_file_service_ping(file_app):
    client = TestClient(file_app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.text == '"PONG"'


def test_file_service_root(file_app):
    client = TestClient(file_app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["file_service"] == "Running"

