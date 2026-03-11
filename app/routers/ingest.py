from typing import List
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import verify_api_key
from app.schemas import NetworkDataRequest, BatchNetworkDataRequest, BatchNetworkDataResponse
from app.utils import parse_timestamp, build_reading

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Ingest"])


@router.post("/network-data", response_model=dict)
def create_network_data(
    data: NetworkDataRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Ingest a single sensor reading.

    Accepts one `NetworkDataRequest` payload and writes it to the database.
    Returns the auto-generated record `id` on success.
    """
    try:
        ts = parse_timestamp(data.timestamp)
        db_reading = build_reading(data, ts)
        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)
        logger.info(f"Data saved for source {data.source}, ID: {db_reading.id}")
        return {"message": "Data saved successfully", "id": db_reading.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/network-data/batch", response_model=BatchNetworkDataResponse)
def create_batch_network_data(
    batch_data: BatchNetworkDataRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Ingest up to 100 sensor readings in one request.

    Each reading is validated independently. The entire valid set is committed
    in a single transaction; if the commit fails all readings in the batch are
    marked as failed. Per-reading validation failures do **not** abort the
    rest of the batch.
    """
    successful = 0
    failed = 0
    details: List[dict] = []
    db_readings: List[tuple] = []

    for idx, data in enumerate(batch_data.readings):
        try:
            ts = parse_timestamp(data.timestamp)
            db_readings.append((idx, data.source, build_reading(data, ts)))
        except HTTPException as e:
            failed += 1
            details.append({"index": idx, "source": data.source, "status": "failed", "error": e.detail})
        except Exception as e:
            failed += 1
            details.append({"index": idx, "source": data.source, "status": "failed", "error": str(e)})

    if db_readings:
        try:
            for _, _, reading in db_readings:
                db.add(reading)
            db.commit()
            for idx, source, reading in db_readings:
                db.refresh(reading)
                successful += 1
                details.append({"index": idx, "source": source, "status": "success", "id": reading.id})
            logger.info(f"Batch processed: {successful} successful, {failed} failed")
        except Exception as e:
            db.rollback()
            failed += len(db_readings)
            logger.error(f"Batch commit error: {str(e)}")
            details = [
                {"index": idx, "source": src, "status": "failed", "error": "Database commit error"}
                for idx, src, _ in db_readings
            ] + [d for d in details if d["status"] == "failed"]

    return BatchNetworkDataResponse(
        total_submitted=len(batch_data.readings),
        successful=successful,
        failed=failed,
        details=details,
    )