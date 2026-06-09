from datetime import datetime
from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert
from app.database import SessionLocal
from app.models import (
    DeviceReading,
    UserDevice,
    CoverageRequest,
    CoverageRequestContribution
)
from decimal import Decimal
from app.services import create_reward_transaction 

# --------------- FETCH PENDING READINGS --------------- #
def fetch_pending_readings(db, limit=1000):
    readings = (
        db.query(DeviceReading)
        .filter(
            or_(
                DeviceReading.processing_status == "PENDING",
                DeviceReading.processing_status.is_(None)
            )
        )
        .order_by(DeviceReading.created_at.asc())
        .limit(limit)
        .all()
    )
    return readings


# --------------- FETCH REQUESTS --------------- #
def fetch_requests_by_ids(db, ids):
    if not ids:
        return []

    requests = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id.in_(ids))
        .all()
    )
    return requests


# --------------- MARK READING PROCESSED --------------- #
def mark_reading_processed(db, reading_id):
    (
        db.query(DeviceReading)
        .filter(DeviceReading.id == reading_id)
        .update({
            "processing_status": "PROCESSED"
        })
    )


# --------------- MARK READING REJECTED --------------- #
def mark_reading_rejected(db, reading_id):
    (
        db.query(DeviceReading)
        .filter(DeviceReading.id == reading_id)
        .update({
            "processing_status": "REJECTED"
        })
    )


# --------------- UPDATE REQUEST SCORE --------------- #
def update_request_score(db, request_id, delta):

    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if not request:
        return None

    request.current_density_score += delta

    db.flush()

    return request.current_density_score


# --------------- UPSERT CONTRIBUTION --------------- #
def upsert_contribution(db, request_id, device_id, delta):
    """
    Update or create contribution row.

    if already created, Adds:
    - total_readings += 1
    - density_contribution += delta
    """
    contribution = (
        db.query(CoverageRequestContribution)
        .filter(
            CoverageRequestContribution.request_id == request_id,
            CoverageRequestContribution.device_id == device_id
        )
        .first()
    )

    if contribution:

        contribution.total_readings += 1
        contribution.density_contribution += delta
        contribution.updated_at = datetime.utcnow()

    else:

        contribution = CoverageRequestContribution(
            request_id=request_id,
            device_id=device_id,
            total_readings=1,
            density_contribution=delta,
            reward_share=0
        )

        db.add(contribution)



# --------------- COMPLETE REQUEST --------------- #
def complete_request(db, request_id):
    request = (
        db.query(CoverageRequest)
        .filter(CoverageRequest.id == request_id)
        .with_for_update()   # add this
        .first()
    )

    if not request or request.status == "COMPLETED":
        return

    request.status = "COMPLETED"
    request.completed_at = datetime.utcnow()

    db.flush()  # write status before distributing

    distribute_rewards(db, request)


# --------------- DISTRIBUTE REWARD --------------- #
def distribute_rewards(db, request):
    contributions = (
        db.query(CoverageRequestContribution)
        .filter(CoverageRequestContribution.request_id == request.id)
        .all()
    )

    if not contributions:
        return

    total_density = sum(c.density_contribution for c in contributions)

    if total_density <= 0:
        return

    reward_pool = Decimal(str(request.reward_amount))

    for contribution in contributions:
        share = Decimal(str(contribution.density_contribution)) / Decimal(str(total_density))
        reward_amount = (reward_pool * share).quantize(Decimal("0.01"))

        if reward_amount <= 0:
            continue

        # look up the user_id from device_id
        device = (
            db.query(UserDevice)
            .filter(UserDevice.device_id == contribution.device_id)
            .first()
        )

        if not device:
            continue  # device was never linked to an account

        contribution.reward_share = float(share)

        try:
            create_reward_transaction(
                db=db,
                user_id=device.user_id,
                amount=reward_amount,
                description=f"Reward for coverage request #{request.id}",
            )
        except ValueError:
            # profile deleted between contribution and completion, skip
            continue
