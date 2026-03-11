# Signal Atlas API

A FastAPI application for collecting and querying mobile network signal data.

**Server:** `https://sa.agentraeg.com`  
**Interactive docs:** `https://sa.agentraeg.com/docs`

---

## Authentication

Every endpoint (except `GET /`) requires an API key passed in the `X-API-Key` header.

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://sa.agentraeg.com/health
```

| Header | Value |
|--------|-------|
| `X-API-Key` | Your secret API key |

Requests without a valid key return `401 Unauthorized`.

---

## Database Schema

Table: **`device_readings`**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `BIGINT` | NO | Primary key, auto-increment |
| `source` | `VARCHAR(50)` | NO | Identifier for the reading origin (device ID, model name, etc.) |
| `timestamp` | `TIMESTAMP` | NO | Measurement time (ISO-8601) |
| `latitude` | `FLOAT` | YES | −90 to 90 |
| `longitude` | `FLOAT` | YES | −180 to 180 |
| `altitude` | `FLOAT` | NO | Metres, −430 to 8 850 |
| `level` | `INTEGER` | YES | Android signal level (0–4) |
| `asu` | `INTEGER` | YES | Arbitrary Strength Unit |
| `rsrp` | `INTEGER` | YES | Reference Signal Received Power (dBm) |
| `rssi` | `INTEGER` | YES | Received Signal Strength Indicator (dBm) |
| `rsrq` | `INTEGER` | YES | Reference Signal Received Quality (dB) |
| `network_type` | `VARCHAR(20)` | YES | e.g. `LTE`, `5G`, `NR` |
| `operator` | `VARCHAR(100)` | YES | Mobile operator name |
| `cell_id` | `VARCHAR(100)` | YES | Cell tower ID |
| `physical_cell_id` | `INTEGER` | YES | Physical Cell ID (PCI) |
| `tracking_area_code` | `INTEGER` | YES | Tracking Area Code (TAC) |
| `country` | `VARCHAR(100)` | YES | Country name |
| `city` | `VARCHAR(100)` | YES | City name |
| `created_at` | `TIMESTAMP` | NO | Row insertion time (server-generated) |

---

## Common Query Parameters (Mobile endpoints)

All three mobile endpoints accept the same optional filter parameters:

| Parameter | Type | Notes |
|-----------|------|-------|
| `operator` | string | Filter by mobile operator name |
| `network_type` | string | e.g. `LTE`, `5G` |
| `period` | string | Time window: `24h` \| `week` \| `month` |
| `source` | string | `measured` \| `prediction` \| `all` |
| `lat` | float | Centre latitude for radius filter (−90 to 90) |
| `lon` | float | Centre longitude for radius filter (−180 to 180) |
| `radius_km` | float | Radius in km around `(lat, lon)` |

---

## Endpoints

### System

#### Health Check
**GET** `/health`

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://sa.agentraeg.com/health
```

**Response `200`:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-03-11T10:30:00.000000"
}
```

---

### Ingest

#### Submit Single Reading
**POST** `/api/network-data`

Submit one sensor reading.

**Headers:**
```
Content-Type: application/json
X-API-Key: YOUR_API_KEY
```

**Request body:**
```json
{
  "source": "device_001",
  "timestamp": "2026-03-11T10:30:00Z",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "altitude": 15.0,
  "level": 4,
  "asu": 20,
  "rsrp": -95,
  "rssi": -65,
  "rsrq": -11,
  "networkType": "LTE",
  "operator": "AT&T",
  "cellId": "12345678",
  "physicalCellId": 123,
  "trackingAreaCode": 456,
  "country": "United States",
  "city": "New York"
}
```

**Field reference:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `source` | string | ✓ | 1–50 characters |
| `timestamp` | string | ✗ | ISO-8601; defaults to server time |
| `latitude` | float | ✗ | −90 to 90 |
| `longitude` | float | ✗ | −180 to 180 |
| `altitude` | float | ✓ | Metres, −430 to 8 850 |
| `level` | integer | ✗ | Signal level |
| `asu` | integer | ✗ | Arbitrary Strength Unit |
| `rsrp` | integer | ✗ | dBm |
| `rssi` | integer | ✗ | dBm |
| `rsrq` | integer | ✗ | dB |
| `networkType` | string | ✗ | Max 20 chars |
| `operator` | string | ✗ | Max 100 chars |
| `cellId` | string | ✗ | Max 100 chars |
| `physicalCellId` | integer | ✗ | PCI |
| `trackingAreaCode` | integer | ✗ | TAC |
| `country` | string | ✗ | Max 100 chars |
| `city` | string | ✗ | Max 100 chars |

**Example:**
```bash
curl -X POST https://sa.agentraeg.com/api/network-data \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "source": "device_001",
    "timestamp": "2026-03-11T10:30:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 15.0,
    "rsrp": -95,
    "rsrq": -11,
    "networkType": "LTE",
    "operator": "AT&T"
  }'
```

**Response `200`:**
```json
{
  "message": "Data saved successfully",
  "id": 1042
}
```

---

#### Submit Batch Readings
**POST** `/api/network-data/batch`

Submit up to **1 000** readings in a single request. Each reading follows the same schema as the single-reading endpoint.

**Example:**
```bash
curl -X POST https://sa.agentraeg.com/api/network-data/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "readings": [
      {
        "source": "device_001",
        "timestamp": "2026-03-11T10:30:00Z",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "altitude": 15.0,
        "rsrp": -95,
        "rsrq": -11,
        "networkType": "LTE"
      },
      {
        "source": "device_002",
        "timestamp": "2026-03-11T10:31:00Z",
        "latitude": 40.7150,
        "longitude": -74.0070,
        "altitude": 22.5,
        "rsrp": -100,
        "rsrq": -14,
        "networkType": "5G"
      }
    ]
  }'
```

**Response `200`:**
```json
{
  "total_submitted": 2,
  "successful": 2,
  "failed": 0,
  "details": [
    { "index": 0, "source": "device_001", "status": "success", "id": 1043 },
    { "index": 1, "source": "device_002", "status": "success", "id": 1044 }
  ]
}
```

Failed readings include an `"error"` key in their detail object and do not abort the rest of the batch.

---

### Mobile

All mobile endpoints are **GET** requests and share the [common query parameters](#common-query-parameters-mobile-endpoints) listed above.

#### Overview
**GET** `/api/mobile/overview`

Returns aggregate signal statistics for the filtered dataset.

**Metrics:**
- `coverage_quality_percent` = (samples with RSRP ≥ −100 dBm ÷ total samples) × 100
- `density_score` = total samples ÷ (π × radius_km²)  *(only when `radius_km` is provided)*

**Example:**
```bash
curl -G https://sa.agentraeg.com/api/mobile/overview \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "period=24h" \
  --data-urlencode "network_type=LTE" \
  --data-urlencode "lat=40.7128" \
  --data-urlencode "lon=-74.0060" \
  --data-urlencode "radius_km=10"
```

**Response `200`:**
```json
{
  "mean_rsrp": -92.4,
  "mean_rsrq": -11.8,
  "coverage_quality_percent": 64.2,
  "measurements_count": 2432,
  "density_score": 7.78
}
```

---

#### Map
**GET** `/api/mobile/map`

Returns geo-located signal samples for rendering a heatmap or scatter plot.

Points are automatically deduplicated onto a ~110 m grid (3 decimal places) and averaged per cell. Response is capped at **5 000 grid cells**.

**Example:**
```bash
curl -G https://sa.agentraeg.com/api/mobile/map \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "period=week" \
  --data-urlencode "operator=AT&T" \
  --data-urlencode "lat=40.7128" \
  --data-urlencode "lon=-74.0060" \
  --data-urlencode "radius_km=25"
```

**Response `200`:**
```json
{
  "points": [
    { "latitude": 40.713, "longitude": -74.006, "rsrp": -95, "rsrq": -12 },
    { "latitude": 40.715, "longitude": -74.007, "rsrp": -88, "rsrq": -10 }
  ]
}
```

---

#### Trends
**GET** `/api/mobile/trends`

Returns a time-series of mean RSRP and RSRQ, bucketed by period:

| `period` | Bucket size |
|----------|------------|
| `24h` | 1 hour |
| `week` | 1 day |
| `month` | 1 day |

**Example:**
```bash
curl -G https://sa.agentraeg.com/api/mobile/trends \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "period=24h" \
  --data-urlencode "source=measured"
```

**Response `200`:**
```json
{
  "points": [
    { "timestamp": "2026-03-11T09:00:00Z", "mean_rsrp": -94.1, "mean_rsrq": -11.3 },
    { "timestamp": "2026-03-11T10:00:00Z", "mean_rsrp": -93.4, "mean_rsrq": -10.8 }
  ]
}
```

---

## Error Reference

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `400` | Validation error (bad timestamp format, out-of-range value, etc.) |
| `401` | Missing or invalid `X-API-Key` |
| `503` | Database unreachable |
| `500` | Internal server error |

Error body:
```json
{ "detail": "Human-readable description of the error" }
```