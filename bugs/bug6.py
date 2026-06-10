"""
validate_api.py  —  Signal Atlas · API ↔ Database validation
=============================================================

Credentials (.env)
------------------
  SIGNAL_API_KEY       X-API-Key for the Signal Atlas API
  SIGNAL_BASE_URL      https://sa.agentraeg.com  (or your VPS URL)
  SUPABASE_URL         https://<ref>.supabase.co          (Project URL)
  SUPABASE_KEY         service_role secret key             (API Settings)
  SUPABASE_DB_PASSWORD database password                   (Database Settings)

  The PostgreSQL connection string is derived automatically:
    postgresql://postgres:<SUPABASE_DB_PASSWORD>@db.<ref>.supabase.co:5432/postgres

Usage
-----
  pip install requests python-dotenv psycopg2-binary sqlalchemy

  python validate_api.py              # run all suites
  python validate_api.py map          # single suite
  python validate_api.py overview
  python validate_api.py trends
  python validate_api.py operators
"""

import math
import os
import re
import sys

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# ---------------------------------------------------------------------------
# Supabase credential resolution
# ---------------------------------------------------------------------------

SUPABASE_URL         = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY         = os.getenv("SUPABASE_KEY", "")       # service_role key
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")


def _derive_postgres_url() -> str:
    """
    Build a direct PostgreSQL URL from SUPABASE_URL + SUPABASE_DB_PASSWORD.

    SUPABASE_URL  = https://abcdefgh.supabase.co
    → host        = db.abcdefgh.supabase.co
    → url         = postgresql://postgres:<pw>@db.abcdefgh.supabase.co:5432/postgres
    """
    match = re.search(r"https://([^.]+)\.supabase\.co", SUPABASE_URL)
    if not match:
        sys.exit(
            "❌  Cannot parse project ref from SUPABASE_URL.\n"
            "    Expected format: https://<ref>.supabase.co"
        )
    ref  = match.group(1)
    host = f"db.{ref}.supabase.co"
    pw   = requests.utils.quote(SUPABASE_DB_PASSWORD, safe="")
    return f"postgresql://postgres:{pw}@{host}:5432/postgres"


# ---------------------------------------------------------------------------
# Signal Atlas API config
# ---------------------------------------------------------------------------

SIGNAL_API_KEY = os.getenv("SIGNAL_API_KEY", "")
BASE_URL       = os.getenv("SIGNAL_BASE_URL", "https://sa.agentraeg.com").rstrip("/")
HEADERS        = {"X-API-Key": SIGNAL_API_KEY, "Accept": "application/json"}

GOOD_RSRP_THRESHOLD = -100   # mirrors app/constants.py

# ---------------------------------------------------------------------------
# Default filter params  (edit to match your test area)
# ---------------------------------------------------------------------------
DEFAULT_PARAMS: dict = {
    "lat":       29.9408,
    "lon":       31.0672,
    "radius_km": 10,
    "period":    "month",
    # "operator":     "Vodafone",
    # "network_type": "LTE",
    # "source":       "measured",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{path}"
    r   = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def db_query(engine, sql: str, params: dict = {}) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


def approx_equal(a, b, tol: float = 0.1) -> bool:
    """Both None, or both numeric and within tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

results: list[dict] = []


def record(name: str, passed: bool, message: str = "", detail: str = ""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {icon}  {name}")
    if message:
        print(f"         {message}")
    if detail and not passed:
        for line in detail.splitlines():
            print(f"         {line}")
    results.append({"name": name, "passed": passed})


# ---------------------------------------------------------------------------
# WHERE clause builder  —  mirrors apply_mobile_filters in app/utils.py
# ---------------------------------------------------------------------------

def build_where(params: dict) -> tuple[str, dict]:
    clauses: list[str] = []
    bind: dict         = {}

    if params.get("operator"):
        clauses.append("operator = :operator")
        bind["operator"] = params["operator"]

    if params.get("network_type"):
        clauses.append("network_type = :network_type")
        bind["network_type"] = params["network_type"]

    period_map = {"24h": "24 hours", "week": "7 days", "month": "30 days"}
    if params.get("period") in period_map:
        clauses.append(f"timestamp >= NOW() - INTERVAL '{period_map[params['period']]}'")

    source = params.get("source", "")
    if source and source.lower() != "all":
        if source.lower() == "measured":
            clauses.append("source != 'predicted'")
        else:
            clauses.append("source = :source")
            bind["source"] = source

    # Haversine radius — mirrors haversine_sql_km in app/utils.py
    lat       = params.get("lat")
    lon       = params.get("lon")
    radius_km = params.get("radius_km")
    if lat is not None and lon is not None and radius_km is not None:
        clauses.append("""
            latitude  IS NOT NULL
            AND longitude IS NOT NULL
            AND (
                6371.0 * 2 * ATAN2(
                    SQRT(
                        POW(SIN((RADIANS(latitude)  - RADIANS(:lat))  / 2), 2)
                        + COS(RADIANS(:lat)) * COS(RADIANS(latitude))
                        * POW(SIN((RADIANS(longitude) - RADIANS(:lon)) / 2), 2)
                    ),
                    SQRT(1 - (
                        POW(SIN((RADIANS(latitude)  - RADIANS(:lat))  / 2), 2)
                        + COS(RADIANS(:lat)) * COS(RADIANS(latitude))
                        * POW(SIN((RADIANS(longitude) - RADIANS(:lon)) / 2), 2)
                    ))
                )
            ) <= :radius_km
        """)
        bind["lat"]       = float(lat)
        bind["lon"]       = float(lon)
        bind["radius_km"] = float(radius_km)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, bind


# ---------------------------------------------------------------------------
# Suite: /api/mobile/overview
# ---------------------------------------------------------------------------

def suite_overview(engine, params: dict):
    print("\n── Overview (/api/mobile/overview) ──────────────────────────────")
    api = api_get("/api/mobile/overview", params)

    where, bind = build_where(params)
    sql = f"""
        SELECT
            ROUND(AVG(rsrp)::numeric, 2)                                     AS mean_rsrp,
            ROUND(AVG(rsrq)::numeric, 2)                                     AS mean_rsrq,
            COUNT(*)                                                          AS total,
            SUM(CASE WHEN rsrp >= {GOOD_RSRP_THRESHOLD} THEN 1 ELSE 0 END)  AS good_count
        FROM device_readings {where}
    """
    db      = db_query(engine, sql, bind)[0]
    total   = int(db["total"] or 0)
    good    = int(db["good_count"] or 0)
    cov_pct = round((good / total) * 100, 2) if total else None
    mean_rsrp = float(db["mean_rsrp"]) if db["mean_rsrp"] is not None else None
    mean_rsrq = float(db["mean_rsrq"]) if db["mean_rsrq"] is not None else None

    record("measurements_count",
           api["measurements_count"] == total,
           f"api={api['measurements_count']}  db={total}")

    record("mean_rsrp",
           approx_equal(api.get("mean_rsrp"), mean_rsrp),
           f"api={api.get('mean_rsrp')}  db={mean_rsrp}")

    record("mean_rsrq",
           approx_equal(api.get("mean_rsrq"), mean_rsrq),
           f"api={api.get('mean_rsrq')}  db={mean_rsrq}")

    record("coverage_quality_percent",
           approx_equal(api.get("coverage_quality_percent"), cov_pct),
           f"api={api.get('coverage_quality_percent')}  db={cov_pct}")

    if params.get("radius_km"):
        area_km2   = math.pi * float(params["radius_km"]) ** 2
        db_density = round(total / area_km2, 4) if total else None
        record("density_score",
               approx_equal(api.get("density_score"), db_density),
               f"api={api.get('density_score')}  db={db_density}")


# ---------------------------------------------------------------------------
# Suite: /api/mobile/map
# ---------------------------------------------------------------------------

def suite_map(engine, params: dict):
    print("\n── Map (/api/mobile/map) ─────────────────────────────────────────")
    api = api_get("/api/mobile/map", params)
    pts = api.get("points", [])

    where, bind = build_where(params)
    # Add the lat/lon NOT NULL guard without duplicating it if already in WHERE
    extra = "AND" if where else "WHERE"
    sql = f"""
        SELECT
            ROUND(CAST(latitude  AS numeric(9,6)), 3) AS lat_cell,
            ROUND(CAST(longitude AS numeric(9,6)), 3) AS lon_cell,
            ROUND(AVG(rsrp)::numeric, 0)              AS mean_rsrp,
            ROUND(AVG(rsrq)::numeric, 0)              AS mean_rsrq
        FROM device_readings
        {where}
        {extra} latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY lat_cell, lon_cell
        ORDER BY lat_cell, lon_cell
    """
    db_rows = db_query(engine, sql, bind)

    record("point count",
           len(pts) == len(db_rows),
           f"api={len(pts)}  db={len(db_rows)}")

    if not pts or not db_rows:
        return

    db_map   = {(float(r["lat_cell"]), float(r["lon_cell"])): r for r in db_rows}
    api_keys = {(round(p["latitude"], 3), round(p["longitude"], 3)) for p in pts}

    mismatches, orphans = [], []
    for p in pts:
        key = (round(p["latitude"], 3), round(p["longitude"], 3))
        if key not in db_map:
            orphans.append(key)
            continue
        db_p = db_map[key]
        if not (approx_equal(p.get("rsrp"), db_p["mean_rsrp"], tol=1)
                and approx_equal(p.get("rsrq"), db_p["mean_rsrq"], tol=1)):
            mismatches.append(
                f"({key}): api rsrp={p.get('rsrp')} db={db_p['mean_rsrp']} | "
                f"api rsrq={p.get('rsrq')} db={db_p['mean_rsrq']}"
            )

    missing = [k for k in db_map if k not in api_keys]

    record("all API points exist in DB",
           len(orphans) == 0,
           f"{len(orphans)} API point(s) absent from DB",
           "\n".join(str(o) for o in orphans[:10]))

    record("rsrp / rsrq values match (±1)",
           len(mismatches) == 0,
           f"{len(mismatches)} point(s) with value drift > 1",
           "\n".join(mismatches[:10]))

    record("no DB points missing from API",
           len(missing) == 0,
           f"{len(missing)} DB point(s) absent from API response",
           "\n".join(str(m) for m in missing[:10]))


# ---------------------------------------------------------------------------
# Suite: /api/mobile/trends
# ---------------------------------------------------------------------------

def suite_trends(engine, params: dict):
    print("\n── Trends (/api/mobile/trends) ───────────────────────────────────")
    api = api_get("/api/mobile/trends", params)
    pts = api.get("points", [])

    period      = params.get("period", "24h")
    trunc_unit  = "hour" if period == "24h" else "day"
    where, bind = build_where(params)

    sql = f"""
        SELECT
            DATE_TRUNC('{trunc_unit}', timestamp) AS bucket,
            ROUND(AVG(rsrp)::numeric, 2)          AS mean_rsrp,
            ROUND(AVG(rsrq)::numeric, 2)          AS mean_rsrq
        FROM device_readings {where}
        GROUP BY bucket
        ORDER BY bucket
    """
    db_rows = db_query(engine, sql, bind)

    record("bucket count",
           len(pts) == len(db_rows),
           f"api={len(pts)}  db={len(db_rows)}")

    if not pts or not db_rows:
        return

    mismatches = []
    for api_pt, db_row in zip(pts, db_rows):
        if not (approx_equal(api_pt.get("mean_rsrp"), db_row["mean_rsrp"])
                and approx_equal(api_pt.get("mean_rsrq"), db_row["mean_rsrq"])):
            mismatches.append(
                f"bucket {db_row['bucket']}: "
                f"api rsrp={api_pt.get('mean_rsrp')} db={db_row['mean_rsrp']} | "
                f"api rsrq={api_pt.get('mean_rsrq')} db={db_row['mean_rsrq']}"
            )

    record("mean_rsrp / mean_rsrq per bucket (±0.1)",
           len(mismatches) == 0,
           f"{len(mismatches)} bucket(s) with value drift",
           "\n".join(mismatches[:10]))


# ---------------------------------------------------------------------------
# Suite: /api/mobile/operators/unique
# ---------------------------------------------------------------------------

def suite_operators(engine, params: dict):
    print("\n── Operators (/api/mobile/operators/unique) ──────────────────────")
    api     = api_get("/api/mobile/operators/unique", {})
    api_ops = sorted(api.get("operators", []))

    db_rows = db_query(
        engine,
        "SELECT DISTINCT operator FROM device_readings "
        "WHERE operator IS NOT NULL ORDER BY operator",
    )
    db_ops = [r["operator"] for r in db_rows]

    record("operator list matches",
           api_ops == db_ops,
           f"api count={len(api_ops)}  db count={len(db_ops)}",
           f"extra in api:   {sorted(set(api_ops) - set(db_ops))}\n"
           f"missing in api: {sorted(set(db_ops) - set(api_ops))}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

SUITES = {
    "overview":  suite_overview,
    "map":       suite_map,
    "trends":    suite_trends,
    "operators": suite_operators,
}

if __name__ == "__main__":
    # Preflight checks
    errors = []
    if not SIGNAL_API_KEY:
        errors.append("SIGNAL_API_KEY is not set")
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL is not set  "
                      "(e.g. https://abcdefgh.supabase.co)")
    if not SUPABASE_DB_PASSWORD:
        errors.append("SUPABASE_DB_PASSWORD is not set  "
                      "(Supabase → Settings → Database → Database password)")
    if errors:
        for e in errors:
            print(f"❌  {e}")
        sys.exit(1)

    # Build engine from Supabase credentials
    engine = create_engine(_derive_postgres_url(), future=True)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅  Supabase database connection OK")
    except Exception as e:
        sys.exit(f"❌  Cannot connect to Supabase: {e}")

    # Suite selection
    requested = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if requested and requested not in SUITES:
        sys.exit(f"❌  Unknown suite '{requested}'. Choose: {', '.join(SUITES)}")
    to_run = {requested: SUITES[requested]} if requested else SUITES

    print(f"\n{'='*60}")
    print(f"  Signal Atlas — API ↔ DB Validation")
    print(f"  API     : {BASE_URL}")
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  Params  : {DEFAULT_PARAMS}")
    print(f"{'='*60}")

    for name, fn in to_run.items():
        try:
            fn(engine, DEFAULT_PARAMS)
        except requests.HTTPError as e:
            print(f"\n  ⚠️  HTTP {e.response.status_code} on /{name}: {e.response.text}")
        except Exception as e:
            print(f"\n  ⚠️  Suite '{name}' crashed: {e}")

    # Summary
    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  — all good 🎉")
    print(f"{'='*60}\n")
    sys.exit(0 if failed == 0 else 1)