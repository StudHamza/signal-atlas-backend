import math
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import verify_api_key
from app.models import DeviceReading
from app.schemas import OverviewResponse, MapResponse, MapPoint, TrendsResponse, TrendPoint, FiltersResponse
from app.utils import apply_mobile_filters
from app.constants import GOOD_RSRP_THRESHOLD, TRENDS_TRUNC
from sqlalchemy import Integer, Float, Numeric, func

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mobile", tags=["Mobile"])

_FILTER_PARAMS = dict(
    operator=Query(None),
    network_type=Query(None),
    period=Query(None, pattern="^(24h|week|month)$"),
    source=Query(None, description="measured | prediction | all"),
    lat=Query(None, ge=-90, le=90),
    lon=Query(None, ge=-180, le=180),
    radius_km=Query(None, gt=0),
)


@router.get("/overview", response_model=OverviewResponse)
def mobile_overview(
    operator: Optional[str] = Query(None),
    network_type: Optional[str] = Query(None),
    period: Optional[str] = Query(None, pattern="^(24h|week|month)$"),
    source: Optional[str] = Query(None, description="measured | prediction | all"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Aggregate signal overview for the given filters.

    - **mean_rsrp** / **mean_rsrq**: average values across matching samples
    - **coverage_quality_percent**: % of samples with RSRP ≥ -100 dBm
    - **density_score**: samples per km² (only when `radius_km` is provided)
    - **measurements_count**: total matching samples
    """
    try:
        q = apply_mobile_filters(
            db.query(DeviceReading),
            operator, network_type, period, source, lat, lon, radius_km,
        )
        agg = q.with_entities(
            func.avg(DeviceReading.rsrp).label("mean_rsrp"),
            func.avg(DeviceReading.rsrq).label("mean_rsrq"),
            func.count(DeviceReading.id).label("total"),
            func.sum(
                func.cast(DeviceReading.rsrp >= GOOD_RSRP_THRESHOLD, Integer)
            ).label("good_count"),
        ).one()

        total = agg.total or 0
        good = agg.good_count or 0
        coverage_pct = round((good / total) * 100, 2) if total else None
        density: Optional[float] = None
        if radius_km and total:
            area_km2 = math.pi * radius_km ** 2
            density = round(total / area_km2, 4)

        return OverviewResponse(
            mean_rsrp=round(agg.mean_rsrp, 2) if agg.mean_rsrp is not None else None,
            mean_rsrq=round(agg.mean_rsrq, 2) if agg.mean_rsrq is not None else None,
            coverage_quality_percent=coverage_pct,
            measurements_count=total,
            density_score=density,
        )
    except Exception as e:
        logger.error(f"Overview error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/map", response_model=MapResponse)
def mobile_map(
    operator: Optional[str] = Query(None),
    network_type: Optional[str] = Query(None),
    period: Optional[str] = Query(None, pattern="^(24h|week|month)$"),
    source: Optional[str] = Query(None),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Geo-located signal samples filtered by the given criteria.

    Points are deduplicated by rounding coordinates to ~1 km grid cells
    (3 decimal places) and averaging RSRP / RSRQ per cell.
    Maximum 5 000 points returned.
    """
    try:
        q = apply_mobile_filters(
            db.query(DeviceReading),
            operator, network_type, period, source, lat, lon, radius_km,
        ).filter(
            DeviceReading.latitude.isnot(None),
            DeviceReading.longitude.isnot(None),
        )
        lat_cell = func.round(func.cast(DeviceReading.latitude, Numeric(9, 6)), 3)
        lon_cell = func.round(func.cast(DeviceReading.longitude, Numeric(9, 6)), 3)
        rows = (
            q.with_entities(
                lat_cell.label("lat_cell"),
                lon_cell.label("lon_cell"),
                func.avg(DeviceReading.rsrp).label("mean_rsrp"),
                func.avg(DeviceReading.rsrq).label("mean_rsrq"),
            )
            .group_by(lat_cell, lon_cell)
            .limit(5000)
            .all()
        )
        return MapResponse(
            points=[
                MapPoint(
                    latitude=float(r.lat_cell),
                    longitude=float(r.lon_cell),
                    rsrp=int(round(r.mean_rsrp)) if r.mean_rsrp is not None else None,
                    rsrq=int(round(r.mean_rsrq)) if r.mean_rsrq is not None else None,
                )
                for r in rows
            ]
        )
    except Exception as e:
        logger.error(f"Map error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/trends", response_model=TrendsResponse)
def mobile_trends(
    operator: Optional[str] = Query(None),
    network_type: Optional[str] = Query(None),
    period: Optional[str] = Query(None, pattern="^(24h|week|month)$"),
    source: Optional[str] = Query(None),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Time-series of mean RSRP / RSRQ.

    Bucket size:

    | period  | bucket |
    |---------|--------|
    | `24h`   | 1 hour |
    | `week`  | 1 day  |
    | `month` | 1 day  |
    """
    try:
        trunc_unit = TRENDS_TRUNC.get(period or "24h", "hour")
        q = apply_mobile_filters(
            db.query(DeviceReading),
            operator, network_type, period, source, lat, lon, radius_km,
        )
        dialect = db.bind.dialect.name
        if dialect == "sqlite":
            fmt = "%Y-%m-%dT%H:00:00" if trunc_unit == "hour" else "%Y-%m-%dT00:00:00"
            bucket = func.strftime(fmt, DeviceReading.timestamp).label("bucket")
        else:
            bucket = func.date_trunc(trunc_unit, DeviceReading.timestamp).label("bucket")

        rows = (
            q.with_entities(
                bucket,
                func.avg(DeviceReading.rsrp).label("mean_rsrp"),
                func.avg(DeviceReading.rsrq).label("mean_rsrq"),
            )
            .group_by(bucket)
            .order_by(bucket)
            .all()
        )
        return TrendsResponse(
            points=[
                TrendPoint(
                    timestamp=(r.bucket if isinstance(r.bucket, str) else r.bucket.isoformat()) + "Z",
                    mean_rsrp=round(r.mean_rsrp, 2) if r.mean_rsrp is not None else None,
                    mean_rsrq=round(r.mean_rsrq, 2) if r.mean_rsrq is not None else None,
                )
                for r in rows
            ]
        )
    except Exception as e:
        logger.error(f"Trends error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/operators/unique", response_model=FiltersResponse)
def mobile_filters(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Return all unique non-null operator values stored in the database."""
    rows = (
        db.query(DeviceReading.operator)
        .filter(DeviceReading.operator.isnot(None))
        .distinct()
        .order_by(DeviceReading.operator)
        .all()
    )
    return FiltersResponse(operators=[r.operator for r in rows])