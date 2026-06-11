from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from geoalchemy2.shape import to_shape
from app.auth import verify_api_key, require_user, UserInfo
from app.database import get_db
from app.models import (
    CoverageRequest,
    CoverageRequestContribution,
    CoverageRequestPoint,
    Profile,
)
from app.schemas import (
    CreateCoverageRequest,
    UpdateCoverageRequest,
    DensityScoreRequest,
)
from app.services import (
    create_request,
    fetch_requests,
    update_request
)
from shapely.geometry import shape
from shapely.wkt import dumps


router = APIRouter(
    prefix="/coverage-requests",
    tags=["Coverage Requests"]
)


# GET ALL REQUESTS — public read with API key
@router.get("")
def get_coverage_requests(
    status: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    return fetch_requests(
        db=db,
        status=status,
        country=country,
        city=city,
        sort_by=sort_by
    )


# GET NEARBY REQUESTS — public read with API key
@router.get("/nearby")
def get_nearby_requests(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(5),
    status: Optional[str] = Query("OPEN"),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    radius_meters = radius_km * 1000
    base_query = db.query(CoverageRequest)

    base_query = base_query.filter(
        text("""
            ST_DWithin(
                area,
                ST_SetSRID(
                    ST_MakePoint(:lon, :lat),
                    4326
                )::geography,
                :radius
            )
        """)
    ).params(
        lat=latitude,
        lon=longitude,
        radius=radius_meters
    )

    if status:
        base_query = base_query.filter(CoverageRequest.status == status)
    if country:
        base_query = base_query.filter(CoverageRequest.country == country)
    if city:
        base_query = base_query.filter(CoverageRequest.city == city)

    requests = base_query.all()

    response = []
    for r in requests:
        progress = 0
        if r.target_density_score:
            progress = round(
                (r.current_density_score / r.target_density_score) * 100, 2
            )
        response.append({
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "country": r.country,
            "city": r.city,
            "reward_amount": float(r.reward_amount),
            "initial_density_score": r.initial_density_score,
            "current_density_score": r.current_density_score,
            "target_density_score": r.target_density_score,
            "progress_percentage": progress,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })

    return {"requests": response}


# GET POLYGON DENSITY SCORE — public with API key
@router.post("/density-score")
def get_polygon_density_score(
    payload: DensityScoreRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    try:
        polygon_shape = shape(payload.area.model_dump())
    except Exception as e:
        raise HTTPException(400, f"Invalid polygon geometry: {str(e)}")

    if not polygon_shape.is_valid:
        raise HTTPException(400, "Invalid polygon")

    polygon_wkt = dumps(polygon_shape)

    readings_count = db.execute(
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
        {"polygon": f"SRID=4326;{polygon_wkt}"}
    ).scalar() or 0

    density_score = readings_count * 0.01

    return {
        "readings_count": readings_count,
        "density_score": density_score,
    }


# GET SINGLE REQUEST — public read with API key
@router.get("/{request_id}")
def get_coverage_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Coverage request not found")

    contributors_count = (
        db.query(CoverageRequestContribution)
        .filter(CoverageRequestContribution.request_id == request_id)
        .count()
    )

    progress_percentage = 0
    if request.target_density_score > 0:
        progress_percentage = round(
            (request.current_density_score / request.target_density_score) * 100, 2
        )

    polygon = to_shape(request.area)
    area_geojson = {
        "type": "Polygon",
        "coordinates": [
            [[float(x), float(y)] for x, y in polygon.exterior.coords]
        ],
    }

    return {
        "id": request.id,
        "title": request.title,
        "description": request.description,
        "country": request.country,
        "city": request.city,
        "area": area_geojson,
        "reward_amount": float(request.reward_amount),
        "initial_density_score": request.initial_density_score,
        "current_density_score": request.current_density_score,
        "target_density_score": request.target_density_score,
        "progress_percentage": progress_percentage,
        "status": request.status,
        "contributors_count": contributors_count,
        "created_by": request.created_by,
        "created_by_display": request.created_by_display,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "completed_at": request.completed_at.isoformat() if request.completed_at else None,
    }


# GET REQUEST PROGRESS — public read with API key
@router.get("/{request_id}/progress")
def get_request_progress(
    request_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Coverage request not found")

    contributors_count = (
        db.query(CoverageRequestContribution)
        .filter(CoverageRequestContribution.request_id == request_id)
        .count()
    )

    total_valid_readings = (
        db.query(CoverageRequestPoint)
        .filter(CoverageRequestPoint.request_id == request_id)
        .count()
    )

    progress_percentage = 0
    if request.target_density_score > 0:
        progress_percentage = round(
            (request.current_density_score / request.target_density_score) * 100, 2
        )

    return {
        "request_id": request.id,
        "current_density_score": request.current_density_score,
        "target_density_score": request.target_density_score,
        "progress_percentage": progress_percentage,
        "contributors_count": contributors_count,
        "total_valid_readings": total_valid_readings,
        "status": request.status,
    }


# CREATE REQUEST — requires authenticated user
@router.post("")
def create_coverage_request(
    payload: CreateCoverageRequest,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    payload.created_by = str(user.id)
    profile = db.query(Profile).filter(Profile.id == user.id).first()
    payload.created_by_display = profile.username if profile else None
    return create_request(db=db, payload=payload)


# UPDATE REQUEST — requires authenticated user + ownership
@router.patch("/{request_id}")
def update_coverage_request(
    request_id: int,
    payload: UpdateCoverageRequest,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Coverage request not found")
    if str(request.created_by) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only edit your own coverage requests")

    return update_request(db=db, request_id=request_id, payload=payload)


# DELETE REQUEST — requires authenticated user + ownership
@router.delete("/{request_id}", status_code=204)
def delete_coverage_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: UserInfo = Depends(require_user),
):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Coverage request not found")
    if str(request.created_by) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only delete your own coverage requests")

    db.query(CoverageRequestPoint).filter(
        CoverageRequestPoint.request_id == request_id
    ).delete()
    db.query(CoverageRequestContribution).filter(
        CoverageRequestContribution.request_id == request_id
    ).delete()
    db.delete(request)
    db.commit()


# GET CONTRIBUTIONS — public read with API key
@router.get("/{request_id}/contributions")
def get_request_contributions(
    request_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Coverage request not found")

    contributions = (
        db.query(CoverageRequestContribution)
        .filter(CoverageRequestContribution.request_id == request_id)
        .order_by(CoverageRequestContribution.density_contribution.desc())
        .all()
    )

    response = []
    for contribution in contributions:
        response.append({
            "device_id": contribution.device_id,
            "total_readings": contribution.total_readings,
            "density_contribution": contribution.density_contribution,
            "reward_share": contribution.reward_share,
        })

    return {"request_id": request_id, "contributors": response}


# GET MY CONTRIBUTION — requires authenticated user
@router.get("/{request_id}/my-contribution")
def get_my_contribution(
    request_id: int,
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    _: UserInfo = Depends(require_user),
):
    contribution = (
        db.query(CoverageRequestContribution)
        .filter(
            CoverageRequestContribution.request_id == request_id,
            CoverageRequestContribution.device_id == device_id,
        )
        .first()
    )

    if not contribution:
        return {
            "request_id": request_id,
            "device_id": device_id,
            "total_readings": 0,
            "density_contribution": 0,
            "reward_share": 0,
        }

    return {
        "request_id": request_id,
        "device_id": contribution.device_id,
        "total_readings": contribution.total_readings,
        "density_contribution": contribution.density_contribution,
        "reward_share": contribution.reward_share,
    }
