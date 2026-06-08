from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime
from pydantic import ConfigDict

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
    dbm: Optional[int] = None
    rsrqUncertainty: Optional[float] = None
    rsrpUncertainty: Optional[float] = None
    gpsAccuracy: Optional[float] = None
    request_id: Optional[int] = None
    processing_status: Optional[str] = Field(None, max_length=30)


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
    country: Optional[str]
    city: Optional[str]
    dbm: Optional[int]
    rsrq_uncertainty: Optional[float]
    rsrp_uncertainty: Optional[float]
    gps_accuracy: Optional[float]
    created_at: str


class BatchNetworkDataRequest(BaseModel):
    """Request model for batch processing multiple sensor readings."""

    readings: List[NetworkDataRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Array of sensor readings (max 100 per request)",
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


# Coverage Request

class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: List


class CreateCoverageRequest(BaseModel):
    title: str
    description: Optional[str] = None
    country: str
    city: str
    reward_amount: float
    target_density_score: float
    area: PolygonGeometry
    created_by: str


class UpdateCoverageRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reward_amount: Optional[float] = None
    target_density_score: Optional[float] = None
    status: Optional[str] = None

class CoverageRequestResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    country: str
    city: str
    reward_amount: float
    initial_density_score: float
    current_density_score: float
    target_density_score: float
    progress_percentage: float
    status: str
    created_at: str
    completed_at: Optional[str]

class CoverageRequestSummary(BaseModel):
    id: int
    title: str
    description: Optional[str]
    country: str
    city: str
    reward_amount: float
    initial_density_score: float
    current_density_score: float
    target_density_score: float
    progress_percentage: float
    status: str
    created_at: str
    completed_at: Optional[str]


class NearbyCoverageResponse(BaseModel):
    requests: List[CoverageRequestSummary]

class DensityScoreRequest(BaseModel):
    area: PolygonGeometry

# Profiles and Wallets

class ProfileResponse(BaseModel):
    id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    credits: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    device_ids: list[str] = []

    model_config = ConfigDict(from_attributes=True)

class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserDeviceRegister(BaseModel):
    device_id: str

class AccountByDeviceRequest(BaseModel):
    device_id: str

class AccountByDeviceResponse(BaseModel):
    account_exists: bool
    profile: ProfileResponse | None = None

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)

class LoginResponse(BaseModel):
    profile: ProfileResponse

class CreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    device_id: Optional[str] = Field(default=None, max_length=100)

class UpdateProfileRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)

class RegisterDeviceRequest(BaseModel):
    user_id: str
    device_id: str = Field(..., max_length=100)

class UserDeviceResponse(BaseModel):
    id: int
    user_id: str
    device_id: str
    created_at: Optional[str] = None
    last_seen_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserDevicesResponse(BaseModel):
    devices: list[UserDeviceResponse]

class WalletDetailsResponse(BaseModel):
    credits: Optional[float] = None
    transaction_count: int

class WalletTransactionResponse(BaseModel):
    id: int
    user_id: str

    amount: Optional[float] = None

    transaction_type: str
    status: str

    description: Optional[str] = None

    created_at: Optional[str] = None

class WalletTransactionsResponse(BaseModel):
    transactions: list[WalletTransactionResponse]
