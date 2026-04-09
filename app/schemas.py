from pydantic import BaseModel, Field
from typing import Optional, List


class NetworkDataRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=50)
    timestamp: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude: Optional[float] = None
    level: Optional[int] = None
    asu: Optional[int] = None
    rsrp: Optional[int] = None
    rssi: Optional[int] = None
    rsrq: Optional[int] = None
    networkType: Optional[str] = Field(None, max_length=20)
    operator: Optional[str] = Field(None, max_length=100)
    cellId: Optional[str] = Field(None, max_length=100)
    physicalCellId: Optional[int] = None
    trackingAreaCode: Optional[int] = None
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)


class NetworkDataResponse(BaseModel):
    id: int
    source: str
    timestamp: str
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]
    level: Optional[int]
    asu: Optional[int]
    rsrp: Optional[int]
    rssi: Optional[int]
    rsrq: Optional[int]
    network_type: Optional[str]
    operator: Optional[str]
    cell_id: Optional[str]
    physical_cell_id: Optional[int]
    tracking_area_code: Optional[int]
    created_at: str


class BatchNetworkDataRequest(BaseModel):
    """Request model for batch processing multiple sensor readings."""
    readings: List[NetworkDataRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Array of sensor readings (max 100 per request)"
    )


class BatchNetworkDataResponse(BaseModel):
    """Response model for batch processing results."""
    total_submitted: int
    successful: int
    failed: int
    details: List[dict]


class OverviewResponse(BaseModel):
    mean_rsrp: Optional[float]
    mean_rsrq: Optional[float]
    coverage_quality_percent: Optional[float]
    measurements_count: int
    density_score: Optional[float]


class MapPoint(BaseModel):
    latitude: float
    longitude: float
    rsrp: Optional[int]
    rsrq: Optional[int]


class MapResponse(BaseModel):
    points: List[MapPoint]


class TrendPoint(BaseModel):
    timestamp: str
    mean_rsrp: Optional[float]
    mean_rsrq: Optional[float]


class TrendsResponse(BaseModel):
    points: List[TrendPoint]


class FiltersResponse(BaseModel):
    operators: List[str]


class UserSamplesCountResponse(BaseModel):
    total_samples_count: int


class UserSamplesDeleteResponse(BaseModel):
    success: bool
    deleted_samples_count: int