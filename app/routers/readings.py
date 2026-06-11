import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DeviceReading
from app.utils import reading_to_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Readings"])


@router.get("/readings/history")
def get_reading_history(
    device_id: str = Query(...),
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(DeviceReading)
        .filter(DeviceReading.source == device_id)
        .order_by(DeviceReading.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [reading_to_response(r) for r in rows]


@router.get("/readings/locations")
def get_reading_locations(
    db: Session = Depends(get_db),
):
    subquery = (
        db.query(
            DeviceReading.source,
            func.max(DeviceReading.timestamp).label("max_ts"),
        )
        .filter(
            DeviceReading.latitude.isnot(None),
            DeviceReading.longitude.isnot(None),
        )
        .group_by(DeviceReading.source)
        .subquery()
    )
    rows = (
        db.query(DeviceReading)
        .join(
            subquery,
            (DeviceReading.source == subquery.c.source)
            & (DeviceReading.timestamp == subquery.c.max_ts),
        )
        .all()
    )
    return [
        {
            "device_id": r.source,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "rsrp": r.rsrp,
            "rsrq": r.rsrq,
            "level": r.level,
            "operator": r.operator,
            "network_type": r.network_type,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]


@router.get("/network-data/{device_id}")
def get_network_data(
    device_id: str,
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(DeviceReading)
        .filter(DeviceReading.source == device_id)
        .order_by(DeviceReading.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [reading_to_response(r) for r in rows]
