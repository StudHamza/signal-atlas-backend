"""Tests for system endpoints: / and /health"""


def test_root_returns_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert "version" in body


def test_health_requires_api_key(client):
    resp = client.get("/health")
    assert resp.status_code == 401


def test_health_with_valid_key(client, auth_headers):
    resp = client.get("/health", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


def test_health_with_invalid_key(client):
    resp = client.get("/health", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401