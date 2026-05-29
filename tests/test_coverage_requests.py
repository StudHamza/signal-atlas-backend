"""Tests for the coverage request feature.

NOTE: PostGIS spatial queries (ST_Covers, ST_DWithin, etc.) are not supported
by the SQLite test database. Tests that exercise spatial logic either mock the
relevant functions or seed data directly via the ORM with simple string values
for the area column. The /nearby endpoint requires PostgreSQL + PostGIS and is
skipped unless the --realdb marker is used.
"""

import pytest
pytest.importorskip("geoalchemy2", reason="geoalchemy2 required for coverage request tests")

from unittest.mock import patch, MagicMock
from datetime import datetime

from app.models import (
    CoverageRequest,
    CoverageRequestContribution,
    CoverageRequestPoint,
)

# The create_request service function uses PostGIS queries (ST_Covers) and
# geoalchemy2 from_shape() which produces WKBElement values incompatible with
# SQLite. We mock it at the router level to test HTTP routing/validation.

CREATE_URL = "/coverage-requests"
MOCK_CREATE_RESPONSE = {
    "message": "Coverage request created successfully",
    "request_id": 1,
    "initial_density_score": 0,
    "status": "OPEN",
}


class TestCreateCoverageRequest:
    def test_create_success(self, client, sample_coverage_request):
        with patch("app.routers.coverage_requests.create_request") as mock_create:
            mock_create.return_value = MOCK_CREATE_RESPONSE

            resp = client.post(CREATE_URL, json=sample_coverage_request)
            assert resp.status_code == 200
            body = resp.json()
            assert body["message"] == "Coverage request created successfully"
            assert body["request_id"] == 1
            assert body["status"] == "OPEN"

    def test_create_does_not_require_auth(self, client, sample_coverage_request):
        with patch("app.routers.coverage_requests.create_request") as mock_create:
            mock_create.return_value = MOCK_CREATE_RESPONSE

            resp = client.post(CREATE_URL, json=sample_coverage_request)
            assert resp.status_code == 200

    def test_create_invalid_polygon_empty_coords(self, client):
        payload = {
            "title": "Test",
            "country": "GB",
            "city": "London",
            "reward_amount": 100,
            "target_density_score": 50,
            "area": {"type": "Polygon", "coordinates": []},
            "created_by": "user-1",
        }
        resp = client.post(CREATE_URL, json=payload)
        assert resp.status_code == 400

    def test_create_polygon_too_few_points(self, client):
        payload = {
            "title": "Test",
            "country": "GB",
            "city": "London",
            "reward_amount": 100,
            "target_density_score": 50,
            "area": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [0, 0]]],
            },
            "created_by": "user-1",
        }
        resp = client.post(CREATE_URL, json=payload)
        assert resp.status_code == 400

    def test_create_missing_required_fields_return_422(self, client):
        resp = client.post(CREATE_URL, json={})
        assert resp.status_code == 422

    def test_create_missing_title(self, client):
        payload = {
            "country": "GB",
            "city": "London",
            "reward_amount": 100,
            "target_density_score": 50,
            "area": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "created_by": "user-1",
        }
        resp = client.post(CREATE_URL, json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

LIST_URL = "/coverage-requests"


class TestListCoverageRequests:
    def test_list_empty(self, client):
        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        assert resp.json()["requests"] == []

    def test_list_returns_all(self, client, db_session):
        req = CoverageRequest(
            title="Request A",
            created_by="user-1",
            country="GB",
            city="London",
            area="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            initial_density_score=0,
            current_density_score=5,
            target_density_score=50,
            reward_amount=100,
            status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["title"] == "Request A"
        assert data[0]["country"] == "GB"
        assert data[0]["city"] == "London"
        assert data[0]["reward_amount"] == 100.0
        assert data[0]["progress_percentage"] == 10.0

    def test_list_filter_by_status(self, client, db_session):
        open_req = CoverageRequest(
            title="Open", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        cancelled_req = CoverageRequest(
            title="Cancelled", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="CANCELLED",
        )
        db_session.add_all([open_req, cancelled_req])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?status=OPEN")
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["title"] == "Open"

        resp = client.get(f"{LIST_URL}?status=CANCELLED")
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["title"] == "Cancelled"

    def test_list_filter_by_country(self, client, db_session):
        gb = CoverageRequest(
            title="GB Req", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        us = CoverageRequest(
            title="US Req", created_by="u1", country="US",
            city="NYC", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add_all([gb, us])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?country=US")
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["title"] == "US Req"

    def test_list_filter_by_city(self, client, db_session):
        london = CoverageRequest(
            title="London", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        paris = CoverageRequest(
            title="Paris", created_by="u1", country="FR",
            city="Paris", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add_all([london, paris])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?city=Paris")
        data = resp.json()["requests"]
        assert len(data) == 1
        assert data[0]["title"] == "Paris"

    def test_list_sort_reward_amount(self, client, db_session):
        high = CoverageRequest(
            title="High", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=200, status="OPEN",
        )
        low = CoverageRequest(
            title="Low", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=50, status="OPEN",
        )
        db_session.add_all([high, low])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?sort_by=reward_amount")
        data = resp.json()["requests"]
        assert data[0]["title"] == "High"
        assert data[1]["title"] == "Low"

    def test_list_sort_reward_desc(self, client, db_session):
        high = CoverageRequest(
            title="High", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=200, status="OPEN",
        )
        low = CoverageRequest(
            title="Low", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=50, status="OPEN",
        )
        db_session.add_all([high, low])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?sort_by=reward_amount")
        data = resp.json()["requests"]
        assert data[0]["title"] == "High"
        assert data[1]["title"] == "Low"

    def test_list_sort_created_at_desc(self, client, db_session):
        old = CoverageRequest(
            title="Old", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
            created_at=datetime(2024, 1, 1),
        )
        new = CoverageRequest(
            title="New", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
            created_at=datetime(2025, 1, 1),
        )
        db_session.add_all([old, new])
        db_session.commit()

        resp = client.get(f"{LIST_URL}?sort_by=created_at")
        data = resp.json()["requests"]
        assert data[0]["title"] == "New"
        assert data[1]["title"] == "Old"

    def test_list_default_sort_is_created_at_desc(self, client, db_session):
        old = CoverageRequest(
            title="Old", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
            created_at=datetime(2024, 1, 1),
        )
        new = CoverageRequest(
            title="New", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
            created_at=datetime(2025, 1, 1),
        )
        db_session.add_all([old, new])
        db_session.commit()

        resp = client.get(LIST_URL)
        data = resp.json()["requests"]
        assert data[0]["title"] == "New"
        assert data[1]["title"] == "Old"

    def test_list_zero_target_progress(self, client, db_session):
        req = CoverageRequest(
            title="Zero Target", created_by="u1", country="GB",
            city="London", area="x", target_density_score=0,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(LIST_URL)
        data = resp.json()["requests"]
        assert data[0]["progress_percentage"] == 0

    def test_list_completed_at_included(self, client, db_session):
        completed_at = datetime(2025, 3, 15, 10, 0, 0)
        req = CoverageRequest(
            title="Done", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="COMPLETED",
            completed_at=completed_at,
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(LIST_URL)
        data = resp.json()["requests"]
        assert data[0]["completed_at"] is not None

    def test_list_no_auth_required(self, client, db_session):
        req = CoverageRequest(
            title="No Auth", created_by="u1", country="GB",
            city="London", area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(LIST_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get Single
# ---------------------------------------------------------------------------

class TestGetCoverageRequest:
    def test_get_success(self, client, db_session):
        with patch("app.routers.coverage_requests.to_shape") as mock_to_shape:
            mock_polygon = MagicMock()
            mock_polygon.exterior.coords = [
                (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)
            ]
            mock_to_shape.return_value = mock_polygon

            req = CoverageRequest(
                title="Single Request",
                description="A single request",
                created_by="user-1",
                country="GB",
                city="London",
                area="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                initial_density_score=1.0,
                current_density_score=25.0,
                target_density_score=100.0,
                reward_amount=200,
                status="OPEN",
            )
            db_session.add(req)
            db_session.commit()

            resp = client.get(f"{LIST_URL}/{req.id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["title"] == "Single Request"
            assert body["description"] == "A single request"
            assert body["country"] == "GB"
            assert body["city"] == "London"
            assert body["reward_amount"] == 200.0
            assert body["initial_density_score"] == 1.0
            assert body["current_density_score"] == 25.0
            assert body["target_density_score"] == 100.0
            assert body["progress_percentage"] == 25.0
            assert body["status"] == "OPEN"
            assert body["created_by"] == "user-1"
            assert body["contributors_count"] == 0
            assert "area" in body
            assert body["area"]["type"] == "Polygon"

    def test_get_not_found(self, client):
        resp = client.get(f"{LIST_URL}/9999")
        assert resp.status_code == 404

    def test_get_with_contributors(self, client, db_session):
        with patch("app.routers.coverage_requests.to_shape") as mock_to_shape:
            mock_polygon = MagicMock()
            mock_polygon.exterior.coords = [
                (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)
            ]
            mock_to_shape.return_value = mock_polygon

            req = CoverageRequest(
                title="With Contributors", created_by="u1",
                country="GB", city="London",
                area="x", target_density_score=50,
                reward_amount=100, status="OPEN",
            )
            db_session.add(req)
            db_session.commit()

            contrib = CoverageRequestContribution(
                request_id=req.id, device_id="device-1",
                total_readings=10, density_contribution=0.5,
            )
            db_session.add(contrib)
            db_session.commit()

            resp = client.get(f"{LIST_URL}/{req.id}")
            assert resp.json()["contributors_count"] == 1

    def test_get_no_auth_required(self, client, db_session):
        with patch("app.routers.coverage_requests.to_shape") as mock_to_shape:
            mock_polygon = MagicMock()
            mock_polygon.exterior.coords = [
                (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)
            ]
            mock_to_shape.return_value = mock_polygon

            req = CoverageRequest(
                title="No Auth", created_by="u1",
                country="GB", city="London",
                area="x", target_density_score=50,
                reward_amount=100, status="OPEN",
            )
            db_session.add(req)
            db_session.commit()

            resp = client.get(f"{LIST_URL}/{req.id}")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Update (PATCH)
# ---------------------------------------------------------------------------

class TestUpdateCoverageRequest:
    UPDATE_URL = "/coverage-requests"

    def test_update_title_and_description(self, client, db_session):
        req = CoverageRequest(
            title="Original", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"title": "Updated", "description": "New desc"},
        )
        assert resp.status_code == 200

        db_session.refresh(req)
        assert req.title == "Updated"
        assert req.description == "New desc"

    def test_update_reward_amount(self, client, db_session):
        req = CoverageRequest(
            title="Reward Test", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"reward_amount": 200},
        )
        assert resp.status_code == 200

        db_session.refresh(req)
        assert float(req.reward_amount) == 200.0

    def test_update_target_density_score(self, client, db_session):
        req = CoverageRequest(
            title="Target Test", created_by="u1",
            country="GB", city="London",
            area="x", current_density_score=20,
            target_density_score=50, reward_amount=100,
            status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"target_density_score": 80},
        )
        assert resp.status_code == 200
        db_session.refresh(req)
        assert req.target_density_score == 80

    def test_update_status_to_cancelled(self, client, db_session):
        req = CoverageRequest(
            title="Cancel Test", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"status": "CANCELLED"},
        )
        assert resp.status_code == 200
        db_session.refresh(req)
        assert req.status == "CANCELLED"
        assert req.completed_at is not None

    def test_update_completed_request_rejected(self, client, db_session):
        req = CoverageRequest(
            title="Completed", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="COMPLETED",
            completed_at=datetime.utcnow(),
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"title": "Should not work"},
        )
        assert resp.status_code == 400

    def test_update_not_found(self, client):
        resp = client.patch(
            f"{self.UPDATE_URL}/9999",
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    def test_update_reward_cannot_decrease_after_contributions(self, client, db_session):
        req = CoverageRequest(
            title="Reward Drop", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        contrib = CoverageRequestContribution(
            request_id=req.id, device_id="d1",
            total_readings=1, density_contribution=0.01,
        )
        db_session.add(contrib)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"reward_amount": 50},
        )
        assert resp.status_code == 400

    def test_update_reward_can_decrease_without_contributions(self, client, db_session):
        req = CoverageRequest(
            title="No Contrib", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"reward_amount": 50},
        )
        assert resp.status_code == 200
        db_session.refresh(req)
        assert float(req.reward_amount) == 50.0

    def test_update_target_cannot_be_lower_than_current(self, client, db_session):
        req = CoverageRequest(
            title="Target Drop", created_by="u1",
            country="GB", city="London",
            area="x", current_density_score=30,
            target_density_score=50, reward_amount=100,
            status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"target_density_score": 20},
        )
        assert resp.status_code == 400

    def test_update_invalid_status_rejected(self, client, db_session):
        req = CoverageRequest(
            title="Bad Status", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"status": "INVALID"},
        )
        assert resp.status_code == 400

    def test_update_no_auth_required(self, client, db_session):
        req = CoverageRequest(
            title="No Auth", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.patch(
            f"{self.UPDATE_URL}/{req.id}",
            json={"title": "Updated"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

PROGRESS_URL = "/coverage-requests"


class TestGetProgress:
    def test_progress_success(self, client, db_session):
        req = CoverageRequest(
            title="Progress", created_by="u1",
            country="GB", city="London",
            area="x", current_density_score=25,
            target_density_score=100, reward_amount=100,
            status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{PROGRESS_URL}/{req.id}/progress")
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == req.id
        assert body["current_density_score"] == 25
        assert body["target_density_score"] == 100
        assert body["progress_percentage"] == 25.0
        assert body["contributors_count"] == 0
        assert body["total_valid_readings"] == 0
        assert body["status"] == "OPEN"

    def test_progress_zero_target(self, client, db_session):
        req = CoverageRequest(
            title="Zero Target", created_by="u1",
            country="GB", city="London",
            area="x", current_density_score=0,
            target_density_score=0, reward_amount=100,
            status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{PROGRESS_URL}/{req.id}/progress")
        assert resp.json()["progress_percentage"] == 0

    def test_progress_not_found(self, client):
        resp = client.get(f"{PROGRESS_URL}/9999/progress")
        assert resp.status_code == 404

    def test_progress_empty_contributors(self, client, db_session):
        req = CoverageRequest(
            title="No Contribs", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{PROGRESS_URL}/{req.id}/progress")
        body = resp.json()
        assert body["contributors_count"] == 0

    def test_progress_with_contributors_and_points(self, client, db_session):
        req = CoverageRequest(
            title="With Data", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        contrib = CoverageRequestContribution(
            request_id=req.id, device_id="d1",
            total_readings=5, density_contribution=0.05,
        )
        db_session.add(contrib)

        point = CoverageRequestPoint(
            request_id=req.id, latitude=51.5, longitude=-0.13,
            first_reading_id=1,
        )
        db_session.add(point)
        db_session.commit()

        resp = client.get(f"{PROGRESS_URL}/{req.id}/progress")
        body = resp.json()
        assert body["contributors_count"] == 1
        assert body["total_valid_readings"] == 1

    def test_progress_no_auth_required(self, client, db_session):
        req = CoverageRequest(
            title="No Auth", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{PROGRESS_URL}/{req.id}/progress")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------

CONTRIB_URL = "/coverage-requests"


class TestGetContributions:
    def test_contributions_empty(self, client, db_session):
        req = CoverageRequest(
            title="No Contribs", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{CONTRIB_URL}/{req.id}/contributions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == req.id
        assert body["contributors"] == []

    def test_contributions_with_data(self, client, db_session):
        req = CoverageRequest(
            title="With Contribs", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        contribs = [
            CoverageRequestContribution(
                request_id=req.id, device_id="device-a",
                total_readings=10, density_contribution=0.5,
            ),
            CoverageRequestContribution(
                request_id=req.id, device_id="device-b",
                total_readings=5, density_contribution=0.2,
            ),
        ]
        db_session.add_all(contribs)
        db_session.commit()

        resp = client.get(f"{CONTRIB_URL}/{req.id}/contributions")
        body = resp.json()
        assert len(body["contributors"]) == 2
        assert body["contributors"][0]["device_id"] == "device-a"
        assert body["contributors"][0]["total_readings"] == 10
        assert body["contributors"][0]["density_contribution"] == 0.5

    def test_contributions_sorted_by_density_desc(self, client, db_session):
        req = CoverageRequest(
            title="Sorted", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        contribs = [
            CoverageRequestContribution(
                request_id=req.id, device_id="low",
                total_readings=1, density_contribution=0.01,
            ),
            CoverageRequestContribution(
                request_id=req.id, device_id="high",
                total_readings=50, density_contribution=0.5,
            ),
        ]
        db_session.add_all(contribs)
        db_session.commit()

        resp = client.get(f"{CONTRIB_URL}/{req.id}/contributions")
        devices = [c["device_id"] for c in resp.json()["contributors"]]
        assert devices == ["high", "low"]

    def test_contributions_not_found(self, client):
        resp = client.get(f"{CONTRIB_URL}/9999/contributions")
        assert resp.status_code == 404

    def test_contributions_no_auth_required(self, client, db_session):
        req = CoverageRequest(
            title="No Auth", created_by="u1",
            country="GB", city="London",
            area="x", target_density_score=50,
            reward_amount=100, status="OPEN",
        )
        db_session.add(req)
        db_session.commit()

        resp = client.get(f"{CONTRIB_URL}/{req.id}/contributions")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Nearby – requires PostGIS, does not work on SQLite
# ---------------------------------------------------------------------------

class TestNearbyRequests:
    @pytest.mark.skip(reason="Requires PostGIS (ST_DWithin, ST_MakePoint)")
    def test_nearby(self, client):
        pass
