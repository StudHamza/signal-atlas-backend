import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DeviceReading

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Devices"])


@router.get("/devices")
def get_devices(db: Session = Depends(get_db)):
    distinct_sources = (
        db.query(DeviceReading.source)
        .distinct()
        .order_by(DeviceReading.source)
        .all()
    )
    return [{"device_id": row[0]} for row in distinct_sources if row[0]]
