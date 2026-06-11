import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_user, UserInfo, verify_api_key
from app.models import Profile, UserDevice
from app.schemas import (
    ProfileResponse,
    ProfileUpdate,
    UserDeviceResponse,
    UserDeviceRegister,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


# ---- Profile ----


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    """Get the authenticated user's profile."""
    profile = db.query(Profile).filter(Profile.id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _profile_to_response(profile)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    updates: ProfileUpdate,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    """Update the authenticated user's profile."""
    profile = db.query(Profile).filter(Profile.id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = updates.model_dump(exclude_unset=True)

    if "username" in update_data:
        existing = (
            db.query(Profile)
            .filter(Profile.username == update_data["username"], Profile.id != user.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return _profile_to_response(profile)


# ---- User Devices ----


@router.get("/me/devices", response_model=list[UserDeviceResponse])
def get_my_devices(
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    """Get all devices linked to the authenticated user."""
    devices = (
        db.query(UserDevice)
        .filter(UserDevice.user_id == user.id)
        .order_by(UserDevice.last_seen_at.desc())
        .all()
    )
    return [_device_to_response(d) for d in devices]


@router.post("/me/devices", response_model=UserDeviceResponse, status_code=201)
def register_device(
    payload: UserDeviceRegister,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    """Register a device (by device_id) under the authenticated user.
    A device can only be linked to one account at a time.
    """
    existing_elsewhere = (
        db.query(UserDevice)
        .filter(
            UserDevice.device_id == payload.device_id,
            UserDevice.user_id != user.id,
        )
        .first()
    )
    if existing_elsewhere:
        raise HTTPException(
            status_code=409,
            detail="Device already linked to another account",
        )

    existing = (
        db.query(UserDevice)
        .filter(
            UserDevice.user_id == user.id,
            UserDevice.device_id == payload.device_id,
        )
        .first()
    )
    if existing:
        existing.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return _device_to_response(existing)

    device = UserDevice(
        user_id=user.id,
        device_id=payload.device_id,
        created_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _device_to_response(device)


@router.delete("/me/devices/{device_id}", status_code=204)
def unregister_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    """Unregister a device from the authenticated user."""
    device = (
        db.query(UserDevice)
        .filter(UserDevice.id == device_id, UserDevice.user_id == user.id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()


def _profile_to_response(p: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.id),
        username=p.username,
        display_name=p.display_name,
        avatar_url=p.avatar_url,
        credits=float(p.credits) if p.credits else None,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


def _device_to_response(d: UserDevice) -> UserDeviceResponse:
    return UserDeviceResponse(
        id=d.id,
        user_id=str(d.user_id),
        device_id=d.device_id,
        created_at=d.created_at.isoformat() if d.created_at else None,
        last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
    )
