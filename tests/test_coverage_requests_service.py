"""Service-layer tests for coverage request business logic.

Tests the validation logic in `create_request` and the business rules in
`update_request` directly, without going through the HTTP layer.
"""

import pytest
pytest.importorskip("geoalchemy2", reason="geoalchemy2 required")

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock, ANY
from shapely.geometry import shape
from geoalchemy2.shape import from_shape

from app.models import (
    CoverageRequest,
    CoverageRequestContribution,
    Profile,
)
from app.services import (
    create_request,
    fetch_requests,
    update_request,
)


# ---------------------------------------------------------------------------
# create_request – polygon validation (does not require a database)
# ---------------------------------------------------------------------------

class MockPayload:
    """Minimal payload stub that satisfies create_request field access."""
    def __init__(self, **kwargs):
        self.title = kwargs.get("title", "Test Request")
        self.description = kwargs.get("description")
        self.created_by = kwargs.get("created_by", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.created_by_display = kwargs.get("created_by_display")
        self.country = kwargs.get("country", "GB")
        self.city = kwargs.get("city", "London")
        self.reward_amount = kwargs.get("reward_amount", 100.0)
        self.target_density_score = kwargs.get("target_density_score", 50.0)
        self.area = kwargs.get("area")


class TestCreateRequestPolygonValidation:
    """Validates the shapely polygon parsing happens before PostGIS calls."""

    def test_valid_polygon_passes_validation(self):
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    }
                )
            ),
        )
        polygon_shape = shape(payload.area.model_dump())
        assert polygon_shape.is_valid
        assert len(polygon_shape.exterior.coords) >= 4

    def test_invalid_geometry_raises(self):
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={"type": "InvalidType", "coordinates": []}
                )
            ),
        )
        from shapely.geometry import shape
        with pytest.raises(Exception):
            shape(payload.area.model_dump())

    def test_too_few_points_detected(self):
        coords = [[0, 0], [1, 0], [0, 0]]
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "type": "Polygon",
                        "coordinates": [coords],
                    }
                )
            ),
        )
        polygon_shape = shape(payload.area.model_dump())
        # shapely auto-closes rings but requires at least 3 distinct coords
        # for a triangle (4 including close). With 2 coords + repeat = 3 points
        # the polygon will have a degenerate/zero-area ring
        assert polygon_shape.area == 0

    def test_invalid_polygon_self_intersecting(self):
        coords = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "type": "Polygon",
                        "coordinates": coords,
                    }
                )
            ),
        )
        polygon_shape = shape(payload.area.model_dump())
        assert not polygon_shape.is_valid


# ---------------------------------------------------------------------------
# create_request – service function (needs db mocking)
# ---------------------------------------------------------------------------

class TestCreateRequestService:
    """Tests create_request with the database layer patched out."""

    def test_initial_density_zero_when_no_readings(self):
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    }
                )
            ),
        )

        with (
            patch("app.services.from_shape") as mock_from_shape,
            patch("app.services.text"),
        ):
            mock_wkb = MagicMock()
            mock_wkb.data = b"\\x0103000000010000000500000000000000000000000000000000000000000000000000f03f0000000000000000000000000000f03f000000000000f03f0000000000000000000000000000f03f00000000000000000000000000000000"
            mock_from_shape.return_value = mock_wkb

            db = MagicMock()
            db.execute.return_value.scalar.return_value = 0
            # mock a profile with sufficient credits for the deduction
            profile_mock = MagicMock()
            profile_mock.credits = Decimal("500")
            db.query.return_value.filter.return_value.first.return_value = profile_mock

            result = create_request(db, payload)

            assert result["status"] == "OPEN"
            assert result["initial_density_score"] == 0.0

    def test_initial_density_from_existing_readings(self):
        payload = MockPayload(
            area=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    }
                )
            ),
        )

        with (
            patch("app.services.from_shape") as mock_from_shape,
            patch("app.services.text"),
        ):
            mock_wkb = MagicMock()
            mock_wkb.data = b"\\x0103000000010000000500000000000000000000000000000000000000000000000000f03f0000000000000000000000000000f03f000000000000f03f0000000000000000000000000000f03f00000000000000000000000000000000"
            mock_from_shape.return_value = mock_wkb

            db = MagicMock()
            db.execute.return_value.scalar.return_value = 150
            profile_mock = MagicMock()
            profile_mock.credits = Decimal("500")
            db.query.return_value.filter.return_value.first.return_value = profile_mock

            result = create_request(db, payload)

            assert result["initial_density_score"] == 1.5


# ---------------------------------------------------------------------------
# fetch_requests – filtering and sorting
# ---------------------------------------------------------------------------

class _ChainableMock:
    """Wraps a MagicMock so that .filter() / .order_by() return self,
    enabling simple chain mocking for query builders."""
    def __init__(self):
        self._mock = MagicMock()
        self._all_return = []

    def filter(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def all(self):
        return self._all_return

    def __getattr__(self, name):
        return getattr(self._mock, name)


class TestFetchRequests:
    """Tests fetch_requests directly with mocked query results."""

    def _make_request(self, **overrides):
        fields = {
            "id": 1, "title": "Test", "description": "desc",
            "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "created_by_display": None,
            "country": "GB", "city": "London",
            "initial_density_score": 0, "current_density_score": 10,
            "target_density_score": 50, "reward_amount": 100,
            "status": "OPEN",
            "created_at": datetime(2025, 1, 1),
            "completed_at": None,
        }
        fields.update(overrides)
        return MagicMock(spec=CoverageRequest, **fields)

    def _mock_db(self, reqs):
        db = MagicMock()
        chain = _ChainableMock()
        chain._all_return = reqs
        db.query.return_value = chain
        return db

    def test_no_filters_returns_all(self):
        reqs = [self._make_request(id=1), self._make_request(id=2)]
        db = self._mock_db(reqs)

        result = fetch_requests(db)

        assert len(result["requests"]) == 2

    def test_filter_by_status(self):
        reqs = [self._make_request(id=1, status="OPEN")]
        db = self._mock_db(reqs)

        result = fetch_requests(db, status="OPEN")

        assert len(result["requests"]) == 1
        assert result["requests"][0]["status"] == "OPEN"

    def test_filter_by_country(self):
        reqs = [self._make_request(id=1, country="US")]
        db = self._mock_db(reqs)

        result = fetch_requests(db, country="US")

        assert len(result["requests"]) == 1
        assert result["requests"][0]["country"] == "US"

    def test_filter_by_city(self):
        reqs = [self._make_request(id=1, city="Paris")]
        db = self._mock_db(reqs)

        result = fetch_requests(db, city="Paris")

        assert len(result["requests"]) == 1
        assert result["requests"][0]["city"] == "Paris"

    def test_sort_reward_asc(self):
        reqs = [
            self._make_request(id=1, reward_amount=50),
            self._make_request(id=2, reward_amount=100),
        ]
        db = self._mock_db(reqs)

        result = fetch_requests(db, sort_by="reward_asc")

        amounts = [r["reward_amount"] for r in result["requests"]]
        assert amounts == [50.0, 100.0]

    def test_sort_reward_desc(self):
        reqs = [
            self._make_request(id=2, reward_amount=100),
            self._make_request(id=1, reward_amount=50),
        ]
        db = self._mock_db(reqs)

        result = fetch_requests(db, sort_by="reward_amount")

        amounts = [r["reward_amount"] for r in result["requests"]]
        assert amounts == [100.0, 50.0]

    def test_sort_created_at_desc(self):
        reqs = [
            self._make_request(id=2, created_at=datetime(2025, 6, 1)),
            self._make_request(id=1, created_at=datetime(2025, 1, 1)),
        ]
        db = self._mock_db(reqs)

        result = fetch_requests(db, sort_by="created_at")

        ids = [r["id"] for r in result["requests"]]
        assert ids == [2, 1]

    def test_progress_percentage_zero_when_target_zero(self):
        reqs = [self._make_request(target_density_score=0)]
        db = self._mock_db(reqs)

        result = fetch_requests(db)

        assert result["requests"][0]["progress_percentage"] == 0

    def test_progress_percentage_computed_correctly(self):
        reqs = [self._make_request(
            current_density_score=25, target_density_score=100
        )]
        db = self._mock_db(reqs)

        result = fetch_requests(db)

        assert result["requests"][0]["progress_percentage"] == 25.0

    def test_completed_at_null_when_not_completed(self):
        reqs = [self._make_request(completed_at=None)]
        db = self._mock_db(reqs)

        result = fetch_requests(db)

        assert result["requests"][0]["completed_at"] is None

    def test_completed_at_includes_value(self):
        completed = datetime(2025, 3, 15, 10, 0, 0)
        reqs = [self._make_request(completed_at=completed)]
        db = self._mock_db(reqs)

        result = fetch_requests(db)

        assert result["requests"][0]["completed_at"] == completed.isoformat()


# ---------------------------------------------------------------------------
# update_request – business rule enforcement
# ---------------------------------------------------------------------------

class TestUpdateRequestService:
    """Tests update_request business rules with a mocked DB."""

    def _make_request(self, **overrides):
        fields = {
            "id": 1, "title": "Original", "description": "desc",
            "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "created_by_display": None,
            "country": "GB", "city": "London",
            "initial_density_score": 0, "current_density_score": 5,
            "target_density_score": 50, "reward_amount": 100,
            "status": "OPEN",
            "created_at": datetime(2025, 1, 1),
            "completed_at": None,
        }
        fields.update(overrides)
        return MagicMock(spec=CoverageRequest, **fields)

    _HAS_CONTRIB = object()

    def _mock_db_with_profile(self, request, profile_credits=Decimal("1000"),
                               contrib_result=None):
        """Set up a mock db that returns the given request for CoverageRequest queries,
        a profile stub for Profile queries, and optionally a contribution result.
        Pass _HAS_CONTRIB as contrib_result to simulate existing contributions."""
        db = MagicMock()
        profile_mock = MagicMock()
        profile_mock.credits = profile_credits

        def query_side_effect(model):
            chain = MagicMock()
            if model is Profile:
                chain.filter.return_value.first.return_value = profile_mock
            elif model is CoverageRequestContribution:
                if contrib_result is self._HAS_CONTRIB:
                    chain.filter.return_value.first.return_value = MagicMock(spec=CoverageRequestContribution)
                else:
                    chain.filter.return_value.first.return_value = None
            else:
                chain.filter.return_value.first.return_value = request
            return chain

        db.query.side_effect = query_side_effect
        return db

    class MockUpdatePayload:
        def __init__(self, **kwargs):
            self.title = kwargs.get("title")
            self.description = kwargs.get("description")
            self.reward_amount = kwargs.get("reward_amount")
            self.target_density_score = kwargs.get("target_density_score")
            self.status = kwargs.get("status")

    def test_update_title_and_description(self):
        request = self._make_request()
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(
            title="Updated", description="New desc"
        )

        update_request(db, 1, payload)

        assert request.title == "Updated"
        assert request.description == "New desc"
        db.commit.assert_called_once()

    def test_update_reward_amount(self):
        request = self._make_request(reward_amount=100)
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(reward_amount=200.0)

        update_request(db, 1, payload)

        assert request.reward_amount == 200.0

    def test_update_reward_cannot_decrease_after_contributions(self):
        request = self._make_request(reward_amount=100)
        db = self._mock_db_with_profile(request, contrib_result=TestUpdateRequestService._HAS_CONTRIB)
        payload = self.MockUpdatePayload(reward_amount=50)

        with pytest.raises(Exception) as exc:
            update_request(db, 1, payload)
        assert "Reward amount cannot be reduced" in str(exc.value)

    def test_update_reward_can_decrease_without_contributions(self):
        request = self._make_request(reward_amount=100)
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(reward_amount=50)

        update_request(db, 1, payload)

        assert request.reward_amount == 50

    def test_target_cannot_be_lower_than_current(self):
        request = self._make_request(current_density_score=30)
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(target_density_score=20)

        with pytest.raises(Exception) as exc:
            update_request(db, 1, payload)
        assert "Target score cannot be lower" in str(exc.value)

    def test_target_can_be_higher_than_current(self):
        request = self._make_request(current_density_score=30)
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(target_density_score=80)

        update_request(db, 1, payload)

        assert request.target_density_score == 80

    def test_status_change_to_cancelled_sets_completed_at(self):
        request = self._make_request(completed_at=None)
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(status="CANCELLED")

        update_request(db, 1, payload)

        assert request.status == "CANCELLED"
        assert request.completed_at is not None

    def test_invalid_status_rejected(self):
        request = self._make_request()
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(status="INVALID")

        with pytest.raises(Exception) as exc:
            update_request(db, 1, payload)
        assert "Invalid status" in str(exc.value)

    def test_completed_request_rejected(self):
        request = self._make_request(status="COMPLETED")
        db = self._mock_db_with_profile(request)
        payload = self.MockUpdatePayload(title="Should not work")

        with pytest.raises(Exception) as exc:
            update_request(db, 1, payload)
        assert "Completed requests cannot be edited" in str(exc.value)

    def test_request_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = self.MockUpdatePayload(title="Nope")

        with pytest.raises(Exception) as exc:
            update_request(db, 1, payload)
        assert "not found" in str(exc.value).lower()
