from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])


@router.get("/")
def root():
    """Health ping — no auth required."""
    return {"message": "Network Monitor API is running!", "status": "OK", "version": "2.0.0"}


@router.get("/health")
def health(db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """
    Deep health check.

    Tests the database connection and returns current server time.
    Requires a valid API key.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed")