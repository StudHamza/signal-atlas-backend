from datetime import timedelta

# LTE "acceptable" signal floor in dBm
GOOD_RSRP_THRESHOLD = -100

PERIOD_DELTA: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}

TRENDS_TRUNC: dict[str, str] = {
    "24h": "hour",
    "week": "day",
    "month": "day",
}