from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4
from app.database import get_db
from decimal import Decimal
from datetime import datetime
from app.schemas import (
    ProfileResponse,
    LoginRequest,
    LoginResponse,
    AccountByDeviceRequest,
    AccountByDeviceResponse,
    CreateAccountRequest,
    UpdateProfileRequest,
    RegisterDeviceRequest,
    UserDeviceResponse,
    UserDevicesResponse,
    WalletDetailsResponse,
    WalletTransactionResponse,
    WalletTransactionsResponse,
)
from app.models import (
    Profile,
    UserDevice,
    WalletTransaction,
)

router = APIRouter(prefix="/api")


# LOGIN (Deprecated — use Supabase Auth instead)
@router.post(
    "/auth/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    profile = (
        db.query(Profile)
        .filter(Profile.username == request.username)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    device_ids = [
        d.device_id
        for d in db.query(UserDevice)
        .filter(UserDevice.user_id == profile.id)
        .all()
    ]

    return LoginResponse(
        profile=ProfileResponse(
            id=str(profile.id),
            username=profile.username,
            credits=float(profile.credits) if profile.credits else None,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            device_ids=device_ids,
        )
    )

# GET ACCOUNT BY DEVICE
@router.post(
    "/account/by-device",
    response_model=AccountByDeviceResponse,
)
def get_account_by_device(
    request: AccountByDeviceRequest,
    db: Session = Depends(get_db),
):
    user_device = (
        db.query(UserDevice)
        .filter(UserDevice.device_id == request.device_id)
        .first()
    )

    if not user_device:
        return AccountByDeviceResponse(
            account_exists=False
        )

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_device.user_id)
        .first()
    )

    if not profile:
        return AccountByDeviceResponse(
            account_exists=False
        )

    device_ids = [
        d.device_id
        for d in db.query(UserDevice)
        .filter(UserDevice.user_id == profile.id)
        .all()
    ]

    return AccountByDeviceResponse(
        account_exists=True,
        profile=ProfileResponse(
            id=str(profile.id),
            username=profile.username,
            credits=float(profile.credits) if profile.credits else None,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            device_ids=device_ids,
        ),
    )

# CREATE ACCOUNT PROFILE
@router.post(
    "/account/create",
    response_model=ProfileResponse,
)
def create_account(
    request: CreateAccountRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(Profile)
        .filter(Profile.username == request.username)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    if request.device_id:
        existing_device = (
            db.query(UserDevice)
            .filter(UserDevice.device_id == request.device_id)
            .first()
        )

        if existing_device:
            raise HTTPException(
                status_code=409,
                detail="Device already linked to another account",
            )

    profile = Profile(
        id=uuid4(),
        username=request.username,
        credits=Decimal("0"),
    )

    db.add(profile)
    db.flush()

    device_ids: list[str] = []

    if request.device_id:
        device = UserDevice(
            user_id=profile.id,
            device_id=request.device_id,
        )
        db.add(device)
        device_ids.append(request.device_id)

    db.commit()
    db.refresh(profile)

    return ProfileResponse(
        id=str(profile.id),
        username=profile.username,
        credits=float(profile.credits) if profile.credits else None,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        device_ids=device_ids,
    )


# REGISTER DEVICE TO ACCOUNT
@router.post(
    "/devices/register",
    response_model=UserDeviceResponse,
)
def register_device(
    request: RegisterDeviceRequest,
    db: Session = Depends(get_db),
):
    try:
        user_uuid = UUID(request.user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    if request.device_id:
        device_owner = (
            db.query(UserDevice)
            .filter(UserDevice.device_id == request.device_id)
            .first()
        )

        if device_owner and device_owner.user_id != user_uuid:
            raise HTTPException(
                status_code=409,
                detail="Device already linked to another account",
            )

    device = UserDevice(
        user_id=user_uuid,
        device_id=request.device_id,
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return UserDeviceResponse(
        id=device.id,
        user_id=str(device.user_id),
        device_id=device.device_id,
        created_at=device.created_at.isoformat() if device.created_at else None,
        last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else None,
    )


# GET PROFILE
@router.get(
    "/profile/{id}",
    response_model=ProfileResponse,
)
def get_profile(
    id: str,
    db: Session = Depends(get_db),
):
    try:
        user_uuid = UUID(id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    device_ids = [
        device.device_id
        for device in (
            db.query(UserDevice)
            .filter(UserDevice.user_id == profile.id)
            .all()
        )
    ]

    return ProfileResponse(
        id=str(profile.id),
        username=profile.username,
        credits=float(profile.credits) if profile.credits else None,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        device_ids=device_ids,
    )


# UPDATE USERNAME
@router.patch(
    "/profile/{id}",
    response_model=ProfileResponse,
)
def update_profile(
    id: str,
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
):
    try:
        user_uuid = UUID(id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    existing_username = (
        db.query(Profile)
        .filter(
            Profile.username == request.username,
            Profile.id != user_uuid,
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    profile.username = request.username
    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    device_ids = [
        d.device_id
        for d in db.query(UserDevice)
        .filter(UserDevice.user_id == profile.id)
        .all()
    ]

    return ProfileResponse(
        id=str(profile.id),
        username=profile.username,
        credits=float(profile.credits) if profile.credits else None,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        device_ids=device_ids,
    )


# GET WALLET DETAILS
@router.get(
    "/wallet/{profile_id}",
    response_model=WalletDetailsResponse,
)
def get_wallet_details(
    profile_id: str,
    db: Session = Depends(get_db),
):
    try:
        user_uuid = UUID(profile_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    transaction_count = (
        db.query(func.count(WalletTransaction.id))
        .filter(WalletTransaction.user_id == user_uuid)
        .scalar()
    )

    return WalletDetailsResponse(
        credits=float(profile.credits) if profile.credits else None,
        transaction_count=transaction_count,
    )


# GET WALLET TRANSACTIONS
@router.get(
    "/wallet/{profile_id}/transactions",
    response_model=WalletTransactionsResponse,
)
def get_wallet_transactions(
    profile_id: str,
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    try:
        user_uuid = UUID(profile_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    transactions = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.user_id == user_uuid)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit)
        .all()
    )

    return WalletTransactionsResponse(
        transactions=[
            WalletTransactionResponse(
                id=t.id,
                user_id=str(t.user_id),
                amount=float(t.amount) if t.amount else None,
                transaction_type=t.transaction_type,
                status=t.status,
                description=t.description,
                created_at=t.created_at.isoformat() if t.created_at else None,
            )
            for t in transactions
        ]
    )
