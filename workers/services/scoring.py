from geoalchemy2.shape import to_shape
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import CoverageRequest, CoverageRequestPoint


def find_matching_requests(db, latitude, longitude):
    requests = (
        db.query(CoverageRequest)
        .filter(
            CoverageRequest.status == "OPEN",
            text("""
                ST_Contains(
                    area::geometry,
                    ST_SetSRID(
                        ST_MakePoint(:longitude, :latitude),
                        4326
                    )
                )
            """)
        )
        .params(latitude=latitude, longitude=longitude)
        .all()
    )
    return requests


def compute_reading_score_delta(db, reading, request_id):
    try:
        with db.begin_nested():

            point = CoverageRequestPoint(
                request_id=request_id,
                latitude=reading.latitude,
                longitude=reading.longitude,
                first_reading_id=reading.id
            )

            db.add(point)
            db.flush()

    except IntegrityError:
        # point already counted before
        return 0

    # new unique point
    base = 0.01

    gps_factor = 1.0

    if (
        reading.gps_accuracy
        and reading.gps_accuracy > 50
    ):
        gps_factor = 0.5

    return base * gps_factor
