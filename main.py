from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from datetime import datetime
from typing import Optional, List
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/network_monitor"
)

# Create engine with connection pooling for production
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model


class DeviceReading(Base):
    __tablename__ = "device_readings"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    level = Column(Integer)
    asu = Column(Integer)
    rsrp = Column(Integer)
    rssi = Column(Integer)
    dbm = Column(Integer)
    rsrq = Column(Integer)
    network_type = Column(String(20))
    operator = Column(String(100))
    cell_id = Column(String(100))
    physical_cell_id = Column(Integer)
    tracking_area_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models


class NetworkDataRequest(BaseModel):
    deviceId: str = Field(..., min_length=1, max_length=50)
    timestamp: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    level: Optional[int] = None
    asu: Optional[int] = None
    rsrp: Optional[int] = None
    rssi: Optional[int] = None
    dbm: Optional[int] = None
    rsrq: Optional[int] = None
    networkType: Optional[str] = Field(None, max_length=20)
    operator: Optional[str] = Field(None, max_length=100)
    cellId: Optional[str] = Field(None, max_length=100)
    physicalCellId: Optional[int] = None
    trackingAreaCode: Optional[int] = None


class NetworkDataResponse(BaseModel):
    id: int
    device_id: str
    timestamp: str
    latitude: Optional[float]
    longitude: Optional[float]
    level: Optional[int]
    asu: Optional[int]
    rsrp: Optional[int]
    rssi: Optional[int]
    dbm: Optional[int]
    rsrq: Optional[int]
    network_type: Optional[str]
    operator: Optional[str]
    cell_id: Optional[str]
    physical_cell_id: Optional[int]
    tracking_area_code: Optional[int]
    created_at: str


class BatchNetworkDataRequest(BaseModel):
    """Request model for batch processing multiple sensor readings"""
    readings: List[NetworkDataRequest] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="Array of sensor readings (max 1000 per request)"
    )


class BatchNetworkDataResponse(BaseModel):
    """Response model for batch processing results"""
    total_submitted: int
    successful: int
    failed: int
    details: List[dict]


# Dependency for database session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# FastAPI App
app = FastAPI(
    title="Network Monitor API",
    description="API for collecting and retrieving network signal data",
    version="1.0.0"
)

# CORS Configuration - Update with your frontend domain in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Network Monitor API is running!",
        "status": "OK",
        "version": "1.0.0"
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503, detail="Database connection failed")


@app.post("/api/network-data", response_model=dict)
def create_network_data(data: NetworkDataRequest, db: Session = Depends(get_db)):
    try:
        # Parse timestamp
        if data.timestamp:
            try:
                ts = datetime.fromisoformat(
                    data.timestamp.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid timestamp format")
        else:
            ts = datetime.utcnow()

        db_reading = DeviceReading(
            device_id=data.deviceId,
            timestamp=ts,
            latitude=data.latitude,
            longitude=data.longitude,
            level=data.level,
            asu=data.asu,
            rsrp=data.rsrp,
            rssi=data.rssi,
            dbm=data.dbm,
            rsrq=data.rsrq,
            network_type=data.networkType,
            operator=data.operator,
            cell_id=data.cellId,
            physical_cell_id=data.physicalCellId,
            tracking_area_code=data.trackingAreaCode,
        )

        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)

        logger.info(
            f"Data saved for device {data.deviceId}, ID: {db_reading.id}")
        return {"message": "Data saved successfully", "id": db_reading.id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving data: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/network-data/batch", response_model=BatchNetworkDataResponse)
def create_batch_network_data(batch_data: BatchNetworkDataRequest, db: Session = Depends(get_db)):
    """
    Process multiple sensor readings in a single request.
    
    Supports up to 1000 readings per request. Returns detailed results including
    successful saves and any errors encountered.
    """
    try:
        successful = 0
        failed = 0
        details = []

        db_readings = []

        # First pass: validate and prepare all readings
        for idx, data in enumerate(batch_data.readings):
            try:
                # Parse timestamp
                if data.timestamp:
                    try:
                        ts = datetime.fromisoformat(
                            data.timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        failed += 1
                        details.append({
                            "index": idx,
                            "device_id": data.deviceId,
                            "status": "failed",
                            "error": "Invalid timestamp format"
                        })
                        continue
                else:
                    ts = datetime.utcnow()

                db_reading = DeviceReading(
                    device_id=data.deviceId,
                    timestamp=ts,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    level=data.level,
                    asu=data.asu,
                    rsrp=data.rsrp,
                    rssi=data.rssi,
                    dbm=data.dbm,
                    rsrq=data.rsrq,
                    network_type=data.networkType,
                    operator=data.operator,
                    cell_id=data.cellId,
                    physical_cell_id=data.physicalCellId,
                    tracking_area_code=data.trackingAreaCode,
                )
                db_readings.append((idx, data.deviceId, db_reading))

            except Exception as e:
                failed += 1
                details.append({
                    "index": idx,
                    "device_id": data.deviceId,
                    "status": "failed",
                    "error": str(e)
                })

        # Second pass: bulk insert all validated readings
        if db_readings:
            try:
                # Add all readings to session
                for idx, device_id, db_reading in db_readings:
                    db.add(db_reading)

                # Commit all at once for better performance
                db.commit()

                # Refresh to get IDs
                for idx, device_id, db_reading in db_readings:
                    db.refresh(db_reading)
                    successful += 1
                    details.append({
                        "index": idx,
                        "device_id": device_id,
                        "status": "success",
                        "id": db_reading.id
                    })

                logger.info(
                    f"Batch processed: {successful} successful, {failed} failed")

            except Exception as e:
                db.rollback()
                failed += successful
                successful = 0
                logger.error(f"Batch commit error: {str(e)}")
                details = [
                    {
                        "index": idx,
                        "device_id": device_id,
                        "status": "failed",
                        "error": "Database commit error"
                    }
                    for idx, device_id, _ in db_readings
                ] + details

        return BatchNetworkDataResponse(
            total_submitted=len(batch_data.readings),
            successful=successful,
            failed=failed,
            details=details
        )

    except Exception as e:
        logger.error(f"Batch processing error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/network-data/{device_id}", response_model=List[NetworkDataResponse])
def get_device_data(
    device_id: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    try:
        readings = db.query(DeviceReading)\
            .filter(DeviceReading.device_id == device_id)\
            .order_by(DeviceReading.timestamp.desc())\
            .offset(offset)\
            .limit(min(limit, 1000))\
            .all()

        return [
            NetworkDataResponse(
                id=r.id,
                device_id=r.device_id,
                timestamp=r.timestamp.isoformat(),
                latitude=r.latitude,
                longitude=r.longitude,
                level=r.level,
                asu=r.asu,
                rsrp=r.rsrp,
                rssi=r.rssi,
                dbm=r.dbm,
                rsrq=r.rsrq,
                network_type=r.network_type,
                operator=r.operator,
                cell_id=r.cell_id,
                physical_cell_id=r.physical_cell_id,
                tracking_area_code=r.tracking_area_code,
                created_at=r.created_at.isoformat()
            )
            for r in readings
        ]
    except Exception as e:
        logger.error(f"Error retrieving data: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/devices", response_model=List[dict])
def get_all_devices(db: Session = Depends(get_db)):
    """Get list of all devices with their latest reading timestamp"""
    try:
        from sqlalchemy import func

        devices = db.query(
            DeviceReading.device_id,
            func.max(DeviceReading.timestamp).label('last_reading'),
            func.count(DeviceReading.id).label('reading_count')
        ).group_by(DeviceReading.device_id).all()

        return [
            {
                "device_id": d.device_id,
                "last_reading": d.last_reading.isoformat(),
                "reading_count": d.reading_count
            }
            for d in devices
        ]
    except Exception as e:
        logger.error(f"Error retrieving devices: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
