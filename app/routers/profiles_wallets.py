from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import uuid4
from app.database import get_db
from decimal import Decimal
from datetime import datetime
from app.schemas import (
    ProfileResponse,
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
            id=profile.id,
            username=profile.username,
            credits=profile.credits,
            device_ids=device_ids,
            created_at=profile.created_at,
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
        id=str(uuid4()),
        username=request.username,
        credits=Decimal("0"),
    )

    db.add(profile)
    db.flush()

    device_ids = []

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
        id=profile.id,
        username=profile.username,
        credits=profile.credits,
        device_ids=device_ids,
        created_at=profile.created_at,
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
    profile = (
        db.query(Profile)
        .filter(Profile.id == request.user_id)
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

        if device_owner and device_owner.user_id != request.user_id:
            raise HTTPException(
                status_code=409,
                detail="Device already linked to another account",
            )
    
    device = UserDevice(
        user_id=request.user_id,
        device_id=request.device_id,
    )

    db.add(device)

    db.commit()
    db.refresh(device)

    return UserDeviceResponse.model_validate(device)

# GET PROFILE
@router.get(
    "/profile/{id}",
    response_model=ProfileResponse,
)
def get_profile(
    id: str,
    db: Session = Depends(get_db),
):
    profile = (
        db.query(Profile)
        .filter(Profile.id == id)
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
        id=profile.id,
        username=profile.username,
        credits=profile.credits,
        device_ids=device_ids,
        created_at=profile.created_at,
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
    profile = (
        db.query(Profile)
        .filter(Profile.id == id)
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
            Profile.id != id,
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    profile.username = request.username

    db.commit()
    db.refresh(profile)

    device_ids = [
        d.device_id
        for d in db.query(UserDevice)
        .filter(UserDevice.user_id == profile.id)
        .all()
    ]

    return ProfileResponse(
        id=profile.id,
        username=profile.username,
        credits=profile.credits,
        device_ids=device_ids,
        created_at=profile.created_at,
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
    profile = (
        db.query(Profile)
        .filter(Profile.id == profile_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    transaction_count = (
        db.query(func.count(WalletTransaction.id))
        .filter(WalletTransaction.user_id == profile_id)
        .scalar()
    )

    return WalletDetailsResponse(
        credits=profile.credits,
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
    profile = (
        db.query(Profile)
        .filter(Profile.id == profile_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    transactions = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.user_id == profile_id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit)
        .all()
    )

    return WalletTransactionsResponse(
        transactions=[
            WalletTransactionResponse.model_validate(t)
            for t in transactions
        ]
    )
