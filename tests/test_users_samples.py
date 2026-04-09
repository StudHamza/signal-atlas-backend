"""Tests for user samples endpoints: GET and DELETE /api/mobile/users_samples"""
import pytest


@pytest.fixture()
def seeded_device(client, auth_headers, sample_reading):
    """Insert 3 readings for device-001 and 2 for device-002, return their IDs."""
    device_a = "device-001"
    device_b = "device-002"

    for i in range(3):
        client.post(
            "/api/network-data",
            json={**sample_reading, "source": device_a, "rsrp": -85 - i},
            headers=auth_headers,
        )
    for i in range(2):
        client.post(
            "/api/network-data",
            json={**sample_reading, "source": device_b, "rsrp": -90 - i},
            headers=auth_headers,
        )
    return {"device_a": device_a, "device_b": device_b}


# ---------------------------------------------------------------------------
# GET /api/mobile/users_samples
# ---------------------------------------------------------------------------

class TestGetUserSamples:

    def test_returns_correct_count(self, client, auth_headers, seeded_device):
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total_samples_count"] == 3

    def test_counts_are_isolated_per_device(self, client, auth_headers, seeded_device):
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_b"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total_samples_count"] == 2

    def test_unknown_device_returns_zero(self, client, auth_headers):
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": "nonexistent-device"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total_samples_count"] == 0

    def test_requires_device_id_param(self, client, auth_headers):
        resp = client.get("/api/mobile/users_samples", headers=auth_headers)
        assert resp.status_code == 422

    def test_requires_auth(self, client, seeded_device):
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
        )
        assert resp.status_code == 401

    def test_response_schema(self, client, auth_headers, seeded_device):
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        body = resp.json()
        assert "total_samples_count" in body
        assert isinstance(body["total_samples_count"], int)

    def test_count_reflects_new_ingestion(self, client, auth_headers, sample_reading, seeded_device):
        """Count should increase after another reading is ingested."""
        client.post(
            "/api/network-data",
            json={**sample_reading, "source": seeded_device["device_a"]},
            headers=auth_headers,
        )
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        assert resp.json()["total_samples_count"] == 4


# ---------------------------------------------------------------------------
# DELETE /api/mobile/users_samples
# ---------------------------------------------------------------------------

class TestDeleteUserSamples:

    def test_deletes_correct_count(self, client, auth_headers, seeded_device):
        resp = client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["deleted_samples_count"] == 3

    def test_only_deletes_target_device(self, client, auth_headers, seeded_device):
        """Deleting device_a must not affect device_b's rows."""
        client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_b"]},
            headers=auth_headers,
        )
        assert resp.json()["total_samples_count"] == 2

    def test_count_is_zero_after_deletion(self, client, auth_headers, seeded_device):
        client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        resp = client.get(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        assert resp.json()["total_samples_count"] == 0

    def test_delete_nonexistent_device_returns_zero(self, client, auth_headers):
        resp = client.delete(
            "/api/mobile/users_samples",
            params={"device_id": "nonexistent-device"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["deleted_samples_count"] == 0

    def test_delete_is_idempotent(self, client, auth_headers, seeded_device):
        """Calling DELETE twice should return 0 on the second call."""
        client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        resp = client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_samples_count"] == 0

    def test_requires_device_id_param(self, client, auth_headers):
        resp = client.delete("/api/mobile/users_samples", headers=auth_headers)
        assert resp.status_code == 422

    def test_requires_auth(self, client, seeded_device):
        resp = client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
        )
        assert resp.status_code == 401

    def test_response_schema(self, client, auth_headers, seeded_device):
        resp = client.delete(
            "/api/mobile/users_samples",
            params={"device_id": seeded_device["device_a"]},
            headers=auth_headers,
        )
        body = resp.json()
        assert "success" in body
        assert "deleted_samples_count" in body
        assert isinstance(body["success"], bool)
        assert isinstance(body["deleted_samples_count"], int)