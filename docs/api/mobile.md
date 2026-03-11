# Mobile Analytics Endpoints

All mobile endpoints share the same set of optional query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `operator` | string | Filter by network operator name |
| `network_type` | string | Filter by technology, e.g. `LTE`, `NR` |
| `period` | `24h` \| `week` \| `month` | Restrict to a recent time window |
| `source` | string | Filter by device source; `all` disables the filter |
| `lat` + `lon` + `radius_km` | float | Geo-filter — all three required together |

---

## `GET /api/mobile/overview`

Aggregate signal statistics for the filtered dataset.

**Auth required:** Yes

### Response `200`

| Field | Type | Description |
|-------|------|-------------|
| `mean_rsrp` | float \| null | Average RSRP across matching samples |
| `mean_rsrq` | float \| null | Average RSRQ across matching samples |
| `coverage_quality_percent` | float \| null | % of samples with RSRP ≥ −100 dBm |
| `measurements_count` | int | Total matching samples |
| `density_score` | float \| null | Samples per km² (only when `radius_km` is supplied) |

### Example

```bash
curl "https://your-domain.com/api/mobile/overview?operator=EE&period=week" \
  -H "X-API-Key: your-key"
```

---

## `GET /api/mobile/map`

Geo-located signal samples for map rendering.

**Auth required:** Yes

Points are deduplicated by rounding to a ~110 m grid cell (3 decimal places) and averaging RSRP/RSRQ per cell. Maximum **5 000** points returned.

### Response `200`

```json
{
  "points": [
    { "latitude": 51.507, "longitude": -0.128, "rsrp": -85, "rsrq": -10 }
  ]
}
```

---

## `GET /api/mobile/trends`

Time-series of mean RSRP / RSRQ.

**Auth required:** Yes

Bucket size depends on the `period` parameter:

| `period` | Bucket |
|----------|--------|
| `24h` (default) | 1 hour |
| `week` | 1 day |
| `month` | 1 day |

### Response `200`

```json
{
  "points": [
    { "timestamp": "2024-06-01T11:00:00Z", "mean_rsrp": -87.3, "mean_rsrq": -11.2 },
    { "timestamp": "2024-06-01T12:00:00Z", "mean_rsrp": -84.1, "mean_rsrq": -9.8 }
  ]
}
```