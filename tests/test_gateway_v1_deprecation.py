from starlette.testclient import TestClient


def test_v1_route_available(gateway_app, mock_gateway_http):
    client = TestClient(gateway_app)
    r = client.get("/v1/tenants/any/path")
    assert r.status_code == 200

