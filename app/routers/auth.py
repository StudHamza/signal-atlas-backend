import logging
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_user, UserInfo
from app.constants import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from app.models import Profile, UserDevice
from app.schemas import (
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthRefreshRequest,
    AuthTokenResponse,
    DeviceCheckRequest,
    DeviceCheckResponse,
    ProfileMinimalResponse,
    ProfileResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

SUPABASE_AUTH_URL = f"{SUPABASE_URL}/auth/v1"


def _supabase_headers() -> dict:
    key = SUPABASE_SERVICE_ROLE_KEY or ""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _call_supabase(path: str, body: dict) -> dict:
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase service role key not configured")
    url = f"{SUPABASE_AUTH_URL}/{path}"
    resp = httpx.post(url, headers=_supabase_headers(), json=body, timeout=15)
    if resp.status_code >= 400:
        detail = "Authentication failed"
        try:
            data = resp.json()
            detail = data.get("error_description") or data.get("error") or data.get("msg") or detail
        except Exception:
            pass
        if resp.status_code == 422:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=resp.status_code, detail=detail)
    return resp.json()


def _profile_to_response(p: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.id),
        username=p.username,
        display_name=p.display_name,
        avatar_url=p.avatar_url,
        credits=float(p.credits) if p.credits else None,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
        device_ids=[d.device_id for d in p.devices] if p.devices else [],
    )


def _get_or_create_profile(supabase_user_id: str, supabase_user_email: str | None, db: Session) -> Profile:
    try:
        from uuid import UUID
        user_uuid = UUID(supabase_user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=500, detail="Invalid user ID from auth provider")

    profile = db.query(Profile).filter(Profile.id == user_uuid).first()
    if profile:
        return profile
    profile = Profile(
        id=user_uuid,
        username=supabase_user_email or f"user_{supabase_user_id[:8]}",
        credits=Decimal("0"),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _link_device_to_user(user_id, device_id: str, db: Session):
    if not device_id:
        return
    existing = (
        db.query(UserDevice)
        .filter(UserDevice.device_id == device_id)
        .first()
    )
    if existing:
        if str(existing.user_id) != str(user_id):
            raise HTTPException(
                status_code=409,
                detail="Device already linked to another account",
            )
        existing.last_seen_at = datetime.utcnow()
        db.commit()
        return
    device = UserDevice(
        user_id=user_id,
        device_id=device_id,
        created_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(device)
    db.commit()


@router.post("/register", response_model=AuthTokenResponse, status_code=201)
def register(
    payload: AuthRegisterRequest,
    db: Session = Depends(get_db),
):
    existing_profile = db.query(Profile).filter(Profile.username == payload.username).first()
    if existing_profile:
        raise HTTPException(status_code=409, detail="Username already taken")

    if payload.device_id:
        existing_device = (
            db.query(UserDevice)
            .filter(UserDevice.device_id == payload.device_id)
            .first()
        )
        if existing_device:
            raise HTTPException(
                status_code=409,
                detail="Device already linked to another account",
            )

    supabase_resp = _call_supabase("signup", {
        "email": payload.email,
        "password": payload.password,
        "data": {"username": payload.username},
    })

    supabase_user = supabase_resp.get("user") or supabase_resp.get("id")
    if not supabase_user:
        raise HTTPException(status_code=500, detail="Failed to create user in auth provider")
    user_id = supabase_user.get("id") if isinstance(supabase_user, dict) else str(supabase_user)

    profile = _get_or_create_profile(user_id, payload.email, db)
    profile.username = payload.username
    db.commit()
    db.refresh(profile)

    _link_device_to_user(profile.id, payload.device_id, db)

    return AuthTokenResponse(
        access_token=supabase_resp.get("access_token", ""),
        refresh_token=supabase_resp.get("refresh_token", ""),
        expires_in=supabase_resp.get("expires_in", 3600),
        user=_profile_to_response(profile),
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: AuthLoginRequest,
    db: Session = Depends(get_db),
):
    supabase_resp = _call_supabase("token?grant_type=password", {
        "email": payload.email,
        "password": payload.password,
    })

    supabase_user = supabase_resp.get("user")
    if not supabase_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = supabase_user.get("id")
    email = supabase_user.get("email")
    profile = _get_or_create_profile(user_id, email, db)

    _link_device_to_user(profile.id, payload.device_id, db)

    return AuthTokenResponse(
        access_token=supabase_resp.get("access_token", ""),
        refresh_token=supabase_resp.get("refresh_token", ""),
        expires_in=supabase_resp.get("expires_in", 3600),
        user=_profile_to_response(profile),
    )


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh(
    payload: AuthRefreshRequest,
    db: Session = Depends(get_db),
):
    supabase_resp = _call_supabase("token?grant_type=refresh_token", {
        "refresh_token": payload.refresh_token,
    })

    supabase_user = supabase_resp.get("user")
    if not supabase_user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = supabase_user.get("id")
    email = supabase_user.get("email")
    profile = _get_or_create_profile(user_id, email, db)

    return AuthTokenResponse(
        access_token=supabase_resp.get("access_token", ""),
        refresh_token=supabase_resp.get("refresh_token", ""),
        expires_in=supabase_resp.get("expires_in", 3600),
        user=_profile_to_response(profile),
    )


@router.post("/device-check", response_model=DeviceCheckResponse)
def device_check(
    payload: DeviceCheckRequest,
    db: Session = Depends(get_db),
):
    user_device = (
        db.query(UserDevice)
        .filter(UserDevice.device_id == payload.device_id)
        .first()
    )
    if not user_device:
        return DeviceCheckResponse(has_account=False)

    profile = db.query(Profile).filter(Profile.id == user_device.user_id).first()
    if not profile:
        return DeviceCheckResponse(has_account=False)

    return DeviceCheckResponse(
        has_account=True,
        profile=ProfileMinimalResponse(
            id=str(profile.id),
            username=profile.username,
        ),
    )


@router.post("/logout", status_code=204)
def logout(
    user: UserInfo = Depends(require_user),
):
    return None
