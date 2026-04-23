import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Query
from sqlalchemy import func

from app.models import DeviceReading
from app.schemas import NetworkDataRequest, NetworkDataResponse
from app.constants import PERIOD_DELTA


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Python-side Haversine distance in km (fallback; prefer PostGIS for scale)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_sql_km(lat: float, lon: float):
    """SQLAlchemy column expression for distance in km from (lat, lon). No PostGIS required."""
    R = 6371.0
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    return (
        R
        * 2
        * func.atan2(
            func.sqrt(
                func.pow(
                    func.sin((func.radians(DeviceReading.latitude) - lat_r) / 2), 2
                )
                + func.cos(lat_r)
                * func.cos(func.radians(DeviceReading.latitude))
                * func.pow(
                    func.sin((func.radians(DeviceReading.longitude) - lon_r) / 2), 2
                )
            ),
            func.sqrt(
                1
                - (
                    func.pow(
                        func.sin((func.radians(DeviceReading.latitude) - lat_r) / 2), 2
                    )
                    + func.cos(lat_r)
                    * func.cos(func.radians(DeviceReading.latitude))
                    * func.pow(
                        func.sin((func.radians(DeviceReading.longitude) - lon_r) / 2), 2
                    )
                )
            ),
        )
    )


# ---------------------------------------------------------------------------
# Query filtering
# ---------------------------------------------------------------------------


def apply_mobile_filters(
    query: Query,
    operator: Optional[str],
    network_type: Optional[str],
    period: Optional[str],
    source: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    radius_km: Optional[float],
) -> Query:
    """Apply all common mobile query filters and return the modified query."""
    if operator:
        query = query.filter(DeviceReading.operator == operator)
    if network_type:
        query = query.filter(DeviceReading.network_type == network_type)
    if period and period in PERIOD_DELTA:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - PERIOD_DELTA[period]
        query = query.filter(DeviceReading.timestamp >= cutoff)
    if source and source.lower() != "all":
        if source.lower() == "measured":
            # Returns everything EXCEPT predicted
            query = query.filter(DeviceReading.source != "predicted")
        else:
            # Fallback for specific source types
            query = query.filter(DeviceReading.source == source)
    if lat is not None and lon is not None and radius_km is not None:
        dist = haversine_sql_km(lat, lon)
        query = query.filter(
            DeviceReading.latitude.isnot(None),
            DeviceReading.longitude.isnot(None),
            dist <= radius_km,
        )
    return query


# ---------------------------------------------------------------------------
# Reading helpers
# ---------------------------------------------------------------------------


def parse_timestamp(raw: Optional[str]) -> datetime:
    """Parse ISO-8601 string to datetime; returns utcnow() if raw is None."""
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid timestamp format. Use ISO-8601."
        )


def build_reading(data: NetworkDataRequest, ts: datetime) -> DeviceReading:
    """Construct a DeviceReading ORM object from a request and parsed timestamp."""
    return DeviceReading(
        source=data.source,
        timestamp=ts,
        latitude=data.latitude,
        longitude=data.longitude,
        altitude=data.altitude,
        level=data.level,
        asu=data.asu,
        rsrp=data.rsrp,
        rssi=data.rssi,
        rsrq=data.rsrq,
        network_type=data.networkType,
        operator=data.operator,
        cell_id=data.cellId,
        physical_cell_id=data.physicalCellId,
        tracking_area_code=data.trackingAreaCode,
        country=data.country,
        city=data.city,
        dbm=data.dbm,
        rsrq_uncertainty=data.rsrqUncertainty,
        rsrp_uncertainty=data.rsrpUncertainty,
        gps_accuracy=data.gpsAccuracy,
    )


def reading_to_response(r: DeviceReading) -> NetworkDataResponse:
    """Serialize a DeviceReading ORM object to the API response schema."""
    return NetworkDataResponse(
        id=r.id,
        source=r.source,
        timestamp=r.timestamp.isoformat(),
        latitude=r.latitude,
        longitude=r.longitude,
        altitude=r.altitude,
        level=r.level,
        asu=r.asu,
        rsrp=r.rsrp,
        rssi=r.rssi,
        rsrq=r.rsrq,
        network_type=r.network_type,
        operator=r.operator,
        cell_id=r.cell_id,
        physical_cell_id=r.physical_cell_id,
        tracking_area_code=r.tracking_area_code,
        country=r.country,
        city=r.city,
        dbm=r.dbm,
        rsrq_uncertainty=r.rsrq_uncertainty,
        rsrp_uncertainty=r.rsrp_uncertainty,
        gps_accuracy=r.gps_accuracy,
        created_at=r.created_at.isoformat(),
    )
