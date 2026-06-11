from datetime import datetime
from sqlalchemy import asc, desc, func, text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from app.models import (
    CoverageRequest,
    CoverageRequestContribution,
    Profile,
    WalletTransaction
)
from shapely.wkt import dumps
from decimal import Decimal
from uuid import UUID


def create_request(db: Session, payload):
    # validate polygon
    try:
        polygon_shape = shape(payload.area.model_dump())

    except Exception:
        raise HTTPException(400, "Invalid polygon geometry")

    if not polygon_shape.is_valid:
        raise HTTPException(400, "Invalid polygon")

    if len(polygon_shape.exterior.coords) < 4:
        raise HTTPException(400, "Polygon must have at least 3 points")

    # convert to PostGIS
    area_geography = from_shape(polygon_shape, srid=4326)
    polygon_wkt = dumps(polygon_shape)

    # compute initial density score, score = unique points count * 0.01
    initial_points_count = db.execute(
        text("""
            SELECT COUNT(DISTINCT CONCAT(latitude, ',', longitude))
            FROM device_readings
            WHERE ST_Covers(
                ST_GeogFromText(:polygon),
                ST_SetSRID(
                    ST_MakePoint(longitude, latitude),
                    4326
                )::geography
            )
        """),
        {
            "polygon": f"SRID=4326;{polygon_wkt}"
        }
    ).scalar() or 0

    initial_density_score = initial_points_count * 0.01

    # insert request
    request = CoverageRequest(
        title=payload.title,
        description=payload.description,
        created_by=payload.created_by,
        created_by_display=payload.created_by_display,
        country=payload.country,
        city=payload.city,
        area=area_geography,
        initial_density_score=initial_density_score,
        current_density_score=initial_density_score,
        target_density_score=payload.target_density_score,
        reward_amount=payload.reward_amount,
        status="OPEN"
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    # deduct reward amount from creator's credits
    try:
        user_uuid = UUID(payload.created_by)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid user ID")

    profile = db.query(Profile).filter(Profile.id == user_uuid).first()
    if not profile:
        raise HTTPException(400, "Profile not found")

    amount = Decimal(str(payload.reward_amount))
    if profile.credits < amount:
        request.status = "CANCELLED"
        request.completed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(400, "Insufficient credits")

    profile.credits -= amount
    transaction = WalletTransaction(
        user_id=user_uuid,
        amount=-amount,
        transaction_type="HOLD",
        status="COMPLETED",
        description=f"Held for coverage request #{request.id}",
    )
    db.add(transaction)
    db.commit()

    return {
        "message": "Coverage request created successfully",
        "request_id": request.id,
        "initial_density_score": initial_density_score,
        "status": request.status
    }


def fetch_requests(db: Session, status=None, country=None, city=None, sort_by=None):

    query = db.query(CoverageRequest)

    # filters
    if status:
        query = query.filter(CoverageRequest.status == status)

    if country:
        query = query.filter(CoverageRequest.country == country)

    if city:
        query = query.filter(CoverageRequest.city == city)

    # normalize
    if sort_by:
        sort_by = sort_by.strip().lower()

    # sorting
    if sort_by == "reward_amount":
        query = query.order_by(desc(CoverageRequest.reward_amount))

    elif sort_by == "created_at":
        query = query.order_by(desc(CoverageRequest.created_at))

    elif sort_by == "progress":
        query = query.order_by(
            desc(
                CoverageRequest.current_density_score /
                CoverageRequest.target_density_score
            )
        )

    else:
        # default
        query = query.order_by(desc(CoverageRequest.created_at))

    requests = query.all()


    # response formatting
    response = []

    for request in requests:
        progress_percentage = 0
        if request.target_density_score > 0:
            progress_percentage = round(
                (
                    request.current_density_score /
                    request.target_density_score
                ) * 100,
                2
            )

        response.append({
            "id": request.id,
            "title": request.title,
            "description": request.description,

            "country": request.country,
            "city": request.city,

            "reward_amount": float(request.reward_amount),

            "initial_density_score": request.initial_density_score,
            "current_density_score": request.current_density_score,
            "target_density_score": request.target_density_score,
            "progress_percentage": progress_percentage,

            "status": request.status,

            "created_by": request.created_by,
            "created_by_display": request.created_by_display,

            "created_at": request.created_at.isoformat() if request.created_at else None,
            "completed_at":
                request.completed_at.isoformat()
                if request.completed_at
                else None
        })

    return {
        "requests": response
    }


def update_request(db: Session, request_id, payload):

    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )

    if not request:
        raise HTTPException(
            status_code=404,
            detail="Coverage request not found"
        )

    # prevent editing completed requests
    if request.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Completed requests cannot be edited"
        )

    # title
    if payload.title is not None:
        request.title = payload.title

    # description
    if payload.description is not None:
        request.description = payload.description

    # reward amount — adjust credits by the difference
    if payload.reward_amount is not None:
        contributions_exist = (
            db.query(CoverageRequestContribution)
            .filter(
                CoverageRequestContribution.request_id
                == request_id
            )
            .first()
        )

        # once contributions exist: reward can only increase
        if ( contributions_exist and payload.reward_amount < float(request.reward_amount)):
            raise HTTPException(
                status_code=400,
                detail=("Reward amount cannot be reduced after contributions exist")
            )

        old_amount = Decimal(str(request.reward_amount))
        new_amount = Decimal(str(payload.reward_amount))
        diff = new_amount - old_amount

        if diff != 0:
            try:
                user_uuid = UUID(request.created_by)
            except (ValueError, TypeError):
                raise HTTPException(400, "Invalid user ID on request")

            profile = db.query(Profile).filter(Profile.id == user_uuid).first()
            if not profile:
                raise HTTPException(400, "Profile not found")

            if diff > 0:
                if profile.credits < diff:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient credits. Need {float(diff):.2f} EGP more."
                    )
                profile.credits -= diff
                tx = WalletTransaction(
                    user_id=user_uuid,
                    amount=-diff,
                    transaction_type="HOLD",
                    status="COMPLETED",
                    description=f"Additional hold for coverage request #{request.id}",
                )
            else:
                profile.credits += abs(diff)
                tx = WalletTransaction(
                    user_id=user_uuid,
                    amount=abs(diff),
                    transaction_type="REFUND",
                    status="COMPLETED",
                    description=f"Partial refund for coverage request #{request.id}",
                )
            db.add(tx)

        request.reward_amount = payload.reward_amount

    # target density score
    if payload.target_density_score is not None:

        if (payload.target_density_score < request.current_density_score):
            raise HTTPException(
                status_code=400,
                detail=("Target score cannot be lower than current score")
            )

        request.target_density_score = (
            payload.target_density_score
        )

    # status
    if payload.status is not None:

        allowed = ["OPEN", "CANCELLED"]

        if payload.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail="Invalid status"
            )

        request.status = payload.status

        if payload.status == "CANCELLED":
            request.completed_at = datetime.utcnow()
            # refund held credits
            try:
                user_uuid = UUID(request.created_by)
            except (ValueError, TypeError):
                raise HTTPException(400, "Invalid user ID on request")
            profile = db.query(Profile).filter(Profile.id == user_uuid).first()
            if profile:
                amount = Decimal(str(request.reward_amount))
                profile.credits += amount
                refund = WalletTransaction(
                    user_id=user_uuid,
                    amount=amount,
                    transaction_type="REFUND",
                    status="COMPLETED",
                    description=f"Refund for cancelled coverage request #{request.id}",
                )
                db.add(refund)

    db.commit()

    return {
        "message":
            "Coverage request updated successfully"
    }


# --------------- Profiles and Wallets --------------- #

def create_reward_transaction(
    db,
    user_id: str,
    amount: Decimal,
    description: str,
) -> WalletTransaction:
    profile = (
        db.query(Profile)
        .filter(Profile.id == user_id)
        .first()
    )

    if not profile:
        raise ValueError("Profile not found")

    profile.credits += amount

    transaction = WalletTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type="REWARD",
        status="COMPLETED",
        description=description,
    )

    db.add(transaction)
    db.flush()

    return transaction

def create_withdrawal_transaction(
    db,
    user_id: str,
    amount: Decimal,
    description: str,
) -> WalletTransaction:
    profile = (
        db.query(Profile)
        .filter(Profile.id == user_id)
        .first()
    )

    if not profile:
        raise ValueError("Profile not found")

    if profile.credits < amount:
        raise ValueError("Insufficient credits")

    profile.credits -= amount

    transaction = WalletTransaction(
        user_id=user_id,
        amount=-amount,
        transaction_type="WITHDRAWAL",
        status="COMPLETED",
        description=description,
    )

    db.add(transaction)
    db.flush()

    return transaction
