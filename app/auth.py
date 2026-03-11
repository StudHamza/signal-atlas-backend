import os
import secrets
import logging
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = set(filter(None, os.getenv("API_KEYS", "").split(",")))

if not API_KEYS:
    _default_key = secrets.token_urlsafe(32)
    API_KEYS.add(_default_key)
    logger.warning(f"No API_KEYS env var set. Generated temporary key: {_default_key}")


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate the X-API-Key header against the configured set of keys."""
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key