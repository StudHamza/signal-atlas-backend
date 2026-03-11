from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


class DeviceReading(Base):
    __tablename__ = "device_readings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    level = Column(Integer)
    asu = Column(Integer)
    rsrp = Column(Integer)
    rssi = Column(Integer)
    altitude = Column(Float)
    rsrq = Column(Integer)
    network_type = Column(String(20))
    operator = Column(String(100))
    cell_id = Column(String(100))
    physical_cell_id = Column(Integer)
    tracking_area_code = Column(Integer)
    country = Column(String(100))
    city = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)