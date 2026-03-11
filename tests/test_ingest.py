"""Tests for the ingest endpoints: POST /api/network-data and /batch"""


def test_ingest_single_reading(client, auth_headers, sample_reading):
    resp = client.post("/api/network-data", json=sample_reading, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Data saved successfully"
    assert isinstance(body["id"], int)


def test_ingest_requires_api_key(client, sample_reading):
    resp = client.post("/api/network-data", json=sample_reading)
    assert resp.status_code == 401


def test_ingest_missing_source(client, auth_headers):
    resp = client.post("/api/network-data", json={"rsrp": -90}, headers=auth_headers)
    assert resp.status_code == 422


def test_ingest_source_too_long(client, auth_headers, sample_reading):
    payload = {**sample_reading, "source": "x" * 51}
    resp = client.post("/api/network-data", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_ingest_invalid_latitude(client, auth_headers, sample_reading):
    payload = {**sample_reading, "latitude": 999}
    resp = client.post("/api/network-data", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_ingest_invalid_timestamp(client, auth_headers, sample_reading):
    payload = {**sample_reading, "timestamp": "not-a-date"}
    resp = client.post("/api/network-data", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_ingest_null_timestamp_defaults_to_now(client, auth_headers, sample_reading):
    payload = {**sample_reading, "timestamp": None}
    resp = client.post("/api/network-data", json=payload, headers=auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def test_batch_ingest_success(client, auth_headers, sample_reading):
    payload = {"readings": [sample_reading, {**sample_reading, "source": "device-002"}]}
    resp = client.post("/api/network-data/batch", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_submitted"] == 2
    assert body["successful"] == 2
    assert body["failed"] == 0


def test_batch_partial_failure(client, auth_headers, sample_reading):
    """One reading has a bad timestamp; the rest should still succeed."""
    bad = {**sample_reading, "source": "bad-device", "timestamp": "INVALID"}
    payload = {"readings": [sample_reading, bad]}
    resp = client.post("/api/network-data/batch", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_submitted"] == 2
    assert body["failed"] >= 1


def test_batch_empty_readings_rejected(client, auth_headers):
    resp = client.post("/api/network-data/batch", json={"readings": []}, headers=auth_headers)
    assert resp.status_code == 422


def test_batch_exceeds_max_readings(client, auth_headers, sample_reading):
    payload = {"readings": [sample_reading] * 101}
    resp = client.post("/api/network-data/batch", json=payload, headers=auth_headers)
    assert resp.status_code == 422