"""Tests for mobile analytics endpoints: /overview, /map, /trends"""
import pytest


@pytest.fixture(autouse=True)
def seed_readings(client, auth_headers, sample_reading):
    """Insert a few readings before each mobile test."""
    readings = [
        sample_reading,
        {**sample_reading, "source": "device-002", "rsrp": -110, "rsrq": -15},
        {**sample_reading, "source": "device-003", "rsrp": -95, "rsrq": -8, "operator": "OtherNet"},
    ]
    for r in readings:
        client.post("/api/network-data", json=r, headers=auth_headers)


# ---------------------------------------------------------------------------
# /overview
# ---------------------------------------------------------------------------

def test_overview_returns_expected_fields(client, auth_headers):
    resp = client.get("/api/mobile/overview", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "mean_rsrp" in body
    assert "measurements_count" in body
    assert body["measurements_count"] >= 3


def test_overview_filter_by_operator(client, auth_headers):
    resp = client.get("/api/mobile/overview?operator=TestNet", headers=auth_headers)
    assert resp.status_code == 200


def test_overview_invalid_period_rejected(client, auth_headers):
    resp = client.get("/api/mobile/overview?period=forever", headers=auth_headers)
    assert resp.status_code == 422


def test_overview_requires_auth(client):
    resp = client.get("/api/mobile/overview")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /map
# ---------------------------------------------------------------------------

def test_map_returns_points(client, auth_headers):
    resp = client.get("/api/mobile/map", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body
    assert isinstance(body["points"], list)
    if body["points"]:
        pt = body["points"][0]
        assert "latitude" in pt and "longitude" in pt


def test_map_requires_auth(client):
    resp = client.get("/api/mobile/map")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /trends
# ---------------------------------------------------------------------------

def test_trends_returns_points(client, auth_headers):
    resp = client.get("/api/mobile/trends", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body


def test_trends_week_period(client, auth_headers):
    resp = client.get("/api/mobile/trends?period=week", headers=auth_headers)
    assert resp.status_code == 200


def test_trends_invalid_period(client, auth_headers):
    resp = client.get("/api/mobile/trends?period=year", headers=auth_headers)
    assert resp.status_code == 422