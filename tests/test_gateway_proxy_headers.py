from starlette.testclient import TestClient


def test_gateway_strips_host(gateway_app, mock_gateway_http):
    client = TestClient(gateway_app)
    r = client.get("/v2/tenants/abc/files", headers={"host": "example"})
    assert r.status_code == 200

