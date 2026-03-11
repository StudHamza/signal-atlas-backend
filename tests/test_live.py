"""
Live integration tests — run against a real hosted API.

Usage:
    API_URL=https://your-vps.com API_KEY=your-key pytest tests/test_live.py -v
"""
import os
import pytest
import requests

pytestmark = pytest.mark.live
BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
API_KEY  = os.environ.get("API_KEY", "test-key")
HEADERS  = {"X-API-Key": API_KEY}

SAMPLE = {
    "source": "live-test-device",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "altitude": 20.0,
    "rsrp": -85,
    "rsrq": -10,
    "networkType": "LTE",
    "operator": "TestNet",
}


def test_root():
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200
    assert r.json()["status"] == "OK"


def test_health():
    r = requests.get(f"{BASE_URL}/health", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["database"] == "connected"


def test_ingest_single():
    r = requests.post(f"{BASE_URL}/api/network-data", json=SAMPLE, headers=HEADERS)
    assert r.status_code == 200
    assert "id" in r.json()


def test_ingest_batch():
    payload = {"readings": [SAMPLE, {**SAMPLE, "source": "live-test-device-2"}]}
    r = requests.post(f"{BASE_URL}/api/network-data/batch", json=payload, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["successful"] == 2


def test_mobile_overview():
    r = requests.get(f"{BASE_URL}/api/mobile/overview", headers=HEADERS)
    assert r.status_code == 200
    assert "measurements_count" in r.json()


def test_mobile_map():
    r = requests.get(f"{BASE_URL}/api/mobile/map", headers=HEADERS)
    print("\n", r.json()) 
    assert r.status_code == 200
    assert "points" in r.json()


def test_mobile_trends():
    r = requests.get(f"{BASE_URL}/api/mobile/trends", headers=HEADERS)
    assert r.status_code == 200
    assert "points" in r.json()


def test_auth_rejected():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 401