from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    REAL,
    ForeignKey,
    Numeric,
    UniqueConstraint
)

from app.database import Base
try:
    from geoalchemy2 import Geography
except ImportError:
    from sqlalchemy import String
    Geography = lambda *a, **kw: String()


class DeviceReading(Base):
    __tablename__ = "device_readings"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(50), nullable=False, index=True)

    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    latitude = Column(Float, index=True)
    longitude = Column(Float, index=True)
    altitude = Column(Float)

    level = Column(Integer)
    asu = Column(Integer)
    rsrp = Column(Integer)
    rssi = Column(Integer)
    rsrq = Column(Integer)
    dbm = Column(Integer)

    rsrq_uncertainty = Column(REAL)
    rsrp_uncertainty = Column(REAL)

    gps_accuracy = Column(REAL)

    network_type = Column(String(20))
    operator = Column(String(100))

    cell_id = Column(String(100))
    physical_cell_id = Column(Integer)
    tracking_area_code = Column(Integer)

    country = Column(String(100))
    city = Column(String(100))

    request_id = Column(
        Integer,
        ForeignKey("coverage_requests.id"),
        nullable=True,
        index=True
    )

    # help speed up the search (PENDING, ACCEPTED, REJECTED)
    processing_status = Column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True
    )


class CoverageRequest(Base):
    __tablename__ = "coverage_requests"

    id = Column(Integer, primary_key=True)

    title = Column(String(255), nullable=False)

    description = Column(String)

    created_by = Column(String(100), nullable=False)

    # searchable location metadata
    country = Column(String(100), index=True)
    city = Column(String(100), index=True)

    # polygon area
    area = Column(
        Geography(geometry_type="POLYGON", srid=4326),
        nullable=False
    )

    initial_density_score = Column(Float, default=0)

    current_density_score = Column(Float, default=0)

    target_density_score = Column(Float, nullable=False)

    reward_amount = Column(Numeric(12, 2), nullable=False)

    # (OPEN, COMPLETED, CANCELLED)
    status = Column(String(30), default="OPEN")

    completed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class CoverageRequestContribution(Base):
    __tablename__ = "coverage_request_contributions"

    id = Column(Integer, primary_key=True)

    request_id = Column(
        Integer,
        ForeignKey("coverage_requests.id"),
        nullable=False,
        index=True
    )

    device_id = Column(String(100), nullable=False, index=True)

    total_readings = Column(Integer, default=0)

    density_contribution = Column(Float, default=0)

    reward_share = Column(Float, default=0)

    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # one row per device per request
        UniqueConstraint(
            "request_id",
            "device_id",
            name="uq_request_device"
        ),
    )

class CoverageRequestPoint(Base):
    __tablename__ = "coverage_request_points"

    id = Column(Integer, primary_key=True)

    request_id = Column(
        Integer,
        ForeignKey("coverage_requests.id"),
        nullable=False,
        index=True
    )

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    first_reading_id = Column(
        Integer,
        ForeignKey("device_readings.id"),
        nullable=False
    )

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "latitude",
            "longitude",
            name="uq_request_point"
        ),
    )
