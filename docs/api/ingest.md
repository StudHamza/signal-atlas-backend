# Ingest Endpoints

## `POST /api/network-data`

Ingest a single sensor reading.

**Auth required:** Yes

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string (1–50 chars) | ✅ | Device identifier |
| `timestamp` | ISO-8601 string | — | Defaults to server time if omitted |
| `latitude` | float [−90, 90] | — | |
| `longitude` | float [−180, 180] | — | |
| `altitude` | float | — | Metres |
| `rsrp` | int | — | Reference Signal Received Power (dBm) |
| `rsrq` | int | — | Reference Signal Received Quality |
| `rssi` | int | — | Received Signal Strength Indicator |
| `level` | int | — | Android signal level (0–4) |
| `asu` | int | — | Arbitrary Strength Unit |
| `networkType` | string (max 20) | — | e.g. `LTE`, `NR` |
| `operator` | string (max 100) | — | |
| `cellId` | string (max 100) | — | |
| `physicalCellId` | int | — | |
| `trackingAreaCode` | int | — | |
| `country` | string (max 100) | — | |
| `city` | string (max 100) | — | |
| `dbm` | int | — | Signal strength in dBm (alternative to RSRP) |
| `rsrqUncertainty` | float | — | Uncertainty of RSRQ measurement |
| `rsrpUncertainty` | float | — | Uncertainty of RSRP measurement |
| `gpsAccuracy` | float | — | GPS accuracy in meters |

### Example

```bash
curl -X POST https://your-domain.com/api/network-data \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "device-001",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "rsrp": -85,
    "rsrq": -10,
    "networkType": "LTE",
    "operator": "EE"
  }'
```

### Response `200`

```json
{ "message": "Data saved successfully", "id": 42 }
```

---

## `POST /api/network-data/batch`

Ingest up to **100** readings in a single request.

**Auth required:** Yes

Each reading is validated independently. The valid set is committed in one transaction; a commit failure marks all readings in the batch as failed. Per-reading validation failures do **not** abort the rest.

### Request body

```json
{
  "readings": [
    { "source": "device-001", "rsrp": -85 },
    { "source": "device-002", "rsrp": -102 }
  ]
}
```

### Response `200`

```json
{
  "total_submitted": 2,
  "successful": 2,
  "failed": 0,
  "details": [
    { "index": 0, "source": "device-001", "status": "success", "id": 43 },
    { "index": 1, "source": "device-002", "status": "success", "id": 44 }
  ]
}
```