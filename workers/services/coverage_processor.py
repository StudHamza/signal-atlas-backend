from app.database import SessionLocal

from services.db import (
    fetch_pending_readings,
    mark_reading_processed,
    mark_reading_rejected,
    update_request_score,
    upsert_contribution,
    complete_request,
    distribute_rewards,
)

from services.scoring import (
    compute_reading_score_delta,
    find_matching_requests,
)


def process_pending_readings():
    db = SessionLocal()

    try:
        # fetch unprocessed readings
        readings = fetch_pending_readings(db, limit=1000)

        if not readings:
            return

        for reading in readings:
            completed_ids: set[int] = set()

            try:

                with db.begin_nested():

                    # basic validation
                    if (
                        reading.latitude is None
                        or reading.longitude is None
                    ):
                        mark_reading_rejected(db, reading.id)
                        continue

                    # find all OPEN requests whose polygons contain this point
                    matching_requests = find_matching_requests(
                        db,
                        latitude=reading.latitude,
                        longitude=reading.longitude
                    )

                    # reading doesn't affect any request
                    if not matching_requests:

                        mark_reading_processed(db,reading.id)
                        continue

                    # process each affected request
                    for request in matching_requests:

                        # safety check
                        if request.status != "OPEN":
                            continue

                        # compute incremental score contribution internally handles duplicate detection
                        delta = compute_reading_score_delta(
                            db,
                            reading=reading,
                            request_id=request.id
                        )

                        # duplicate point
                        if delta <= 0:
                            continue

                        # increment request score
                        new_score = update_request_score(
                            db,
                            request_id=request.id,
                            delta=delta
                        )

                        # reward contribution ONLY if user explicitly selected this request
                        if reading.request_id == request.id:

                            upsert_contribution(
                                db,
                                request_id=request.id,
                                device_id=reading.source,
                                delta=delta
                            )

                        # completion check
                        if (
                            new_score >=
                            request.target_density_score
                        ):

                            complete_request(db, request.id)
                            completed_ids.add(request.id)

                    # mark reading fully processed
                    mark_reading_processed(db, reading.id)

                # distribute rewards outside savepoint
                for rid in completed_ids:
                    distribute_rewards(db, rid)

            except Exception as e:

                print(
                    f"[PROCESSING ERROR] "
                    f"reading_id={reading.id} "
                    f"error={str(e)}"
                )

                mark_reading_rejected(db, reading.id)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
