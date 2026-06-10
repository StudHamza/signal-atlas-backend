from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from app.database import get_db
from datetime import datetime
from app.auth import require_user, UserInfo
from app.schemas import (
    ProfileResponse,
    AccountByDeviceRequest,
    AccountByDeviceResponse,
    LegacyUpdateProfileRequest,
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


# GET ACCOUNT BY DEVICE — used by Android for device-first flow
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
        return AccountByDeviceResponse(account_exists=False)

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_device.user_id)
        .first()
    )
    if not profile:
        return AccountByDeviceResponse(account_exists=False)

    return AccountByDeviceResponse(
        account_exists=True,
        profile=ProfileResponse(
            id=str(profile.id),
            username=profile.username,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
        ),
    )


# GET PROFILE — requires authentication, only returns own profile
@router.get(
    "/profile/{id}",
    response_model=ProfileResponse,
)
def get_profile(
    id: str,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    try:
        user_uuid = UUID(id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    if str(user_uuid) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only access your own profile")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

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


# UPDATE USERNAME — requires auth + ownership
@router.patch(
    "/profile/{id}",
    response_model=ProfileResponse,
)
def update_profile(
    id: str,
    request: LegacyUpdateProfileRequest,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    try:
        user_uuid = UUID(id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    if str(user_uuid) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only edit your own profile")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    existing_username = (
        db.query(Profile)
        .filter(
            Profile.username == request.username,
            Profile.id != user_uuid,
        )
        .first()
    )
    if existing_username:
        raise HTTPException(status_code=409, detail="Username already exists")

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


# GET WALLET DETAILS — requires auth + ownership
@router.get(
    "/wallet/{profile_id}",
    response_model=WalletDetailsResponse,
)
def get_wallet_details(
    profile_id: str,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    try:
        user_uuid = UUID(profile_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    if str(user_uuid) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only access your own wallet")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    transaction_count = (
        db.query(func.count(WalletTransaction.id))
        .filter(WalletTransaction.user_id == user_uuid)
        .scalar()
    )

    return WalletDetailsResponse(
        credits=float(profile.credits) if profile.credits else None,
        transaction_count=transaction_count,
    )


# GET WALLET TRANSACTIONS — requires auth + ownership
@router.get(
    "/wallet/{profile_id}/transactions",
    response_model=WalletTransactionsResponse,
)
def get_wallet_transactions(
    profile_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    try:
        user_uuid = UUID(profile_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Profile not found")

    if str(user_uuid) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only access your own transactions")

    profile = (
        db.query(Profile)
        .filter(Profile.id == user_uuid)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

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
