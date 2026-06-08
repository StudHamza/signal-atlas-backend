import os
import secrets
import logging
import time
from typing import Optional
from uuid import UUID

import jwt
import httpx
from fastapi import HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.security.http import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.constants import SUPABASE_URL, SUPABASE_JWT_SECRET

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = set(filter(None, os.getenv("API_KEYS", "").split(",")))

if not API_KEYS:
    _default_key = secrets.token_urlsafe(32)
    API_KEYS.add(_default_key)
    logger.warning(f"No API_KEYS env var set. Generated temporary key: {_default_key}")

bearer_scheme = HTTPBearer(auto_error=False)


class UserInfo(BaseModel):
    id: UUID
    email: Optional[str] = None
    phone: Optional[str] = None


# Simple in-memory cache for JWKS keys
_jwks_cache = {"keys": None, "expires_at": 0}


def _fetch_jwks():
    if not SUPABASE_URL:
        return None
    if time.time() < _jwks_cache["expires_at"] and _jwks_cache["keys"] is not None:
        return _jwks_cache["keys"]
    try:
        resp = httpx.get(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        keys = data.get("keys", [])
        _jwks_cache["keys"] = keys
        _jwks_cache["expires_at"] = time.time() + 3600
        return keys
    except Exception as e:
        logger.warning(f"Failed to fetch JWKS: {e}")
        return None


def _get_jwk_public_key(kid: str):
    keys = _fetch_jwks()
    if not keys:
        return None
    for key in keys:
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    return None


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate the X-API-Key header against the configured set of keys."""
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[UserInfo]:
    """Verify a Supabase JWT token and return the user info.

    Returns None if no token is provided (auth optional).
    Raises 401 if token is invalid.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    if not token:
        return None

    try:
        # First try: validate using JWKS (RS256)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        public_key = _get_jwk_public_key(kid) if kid else None

        if public_key:
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        else:
            # Fallback: HS256 with SUPABASE_JWT_SECRET
            secret = SUPABASE_JWT_SECRET or SUPABASE_URL
            if not secret:
                raise HTTPException(
                    status_code=401,
                    detail="No SUPABASE_JWT_SECRET configured",
                )
            payload = jwt.decode(
                token,
                key=secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")

        return UserInfo(
            id=UUID(user_id),
            email=payload.get("email"),
            phone=payload.get("phone"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.warning(f"JWT verification error: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


def require_user(
    user: Optional[UserInfo] = Depends(get_current_user),
) -> UserInfo:
    """Require a valid authenticated user (raises 401 if not present)."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid Bearer token.",
        )
    return user
