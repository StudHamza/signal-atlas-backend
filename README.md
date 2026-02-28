# Signal Atlas API

A FastAPI application for collecting and retrieving network signal data from devices.

## Overview

The Network Monitor API allows you to:
- Submit single network signal readings from devices
- Batch submit multiple readings (up to 1000 per request)
- Retrieve readings for specific devices
- View all registered devices and their statistics

**Server:** `http://sa.agentraeg.com`

## API Endpoints

### Health Check
**GET** `/health`

Check if the API and database are healthy.

```bash
curl -X GET http://sa.agentraeg.com/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-02-28T10:30:00.000000"
}
```

---

## POST Methods

### 1. Submit Single Reading
**POST** `/api/network-data`

Submit a single network signal reading.

**Request Body:**
```json
{
  "deviceId": "device_001",
  "timestamp": "2024-02-28T10:30:00Z",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "level": 4,
  "asu": 20,
  "rsrp": -95,
  "rssi": -65,
  "dbm": -95,
  "rsrq": 15,
  "networkType": "LTE",
  "operator": "AT&T",
  "cellId": "12345678",
  "physicalCellId": 123,
  "trackingAreaCode": 456
}
```

**Example (curl):**
```bash
curl -X POST http://sa.agentraeg.com/api/network-data \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "device_001",
    "timestamp": "2024-02-28T10:30:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "level": 4,
    "rsrp": -95,
    "networkType": "LTE",
    "operator": "AT&T"
  }'
```

**Response:**
```json
{
  "message": "Data saved successfully",
  "id": 1
}
```

**Field Descriptions:**
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| deviceId | string | ✓ | Device identifier (1-50 chars) |
| timestamp | string | ✗ | ISO 8601 format (defaults to current time) |
| latitude | float | ✗ | -90 to 90 |
| longitude | float | ✗ | -180 to 180 |
| level | integer | ✗ | Signal level |
| asu | integer | ✗ | Arbitrary Strength Unit |
| rsrp | integer | ✗ | Reference Signal Received Power (dBm) |
| rssi | integer | ✗ | Received Signal Strength Indicator (dBm) |
| dbm | integer | ✗ | Signal power in decibels |
| rsrq | integer | ✗ | Reference Signal Received Quality (dB) |
| networkType | string | ✗ | e.g., "LTE", "5G", "4G" |
| operator | string | ✗ | Mobile operator name |
| cellId | string | ✗ | Cell tower ID |
| physicalCellId | integer | ✗ | Physical cell ID |
| trackingAreaCode | integer | ✗ | Tracking area code |

---

### 2. Submit Batch Readings
**POST** `/api/network-data/batch`

Submit multiple readings in one request (max 1000 per request).

**Request Body:**
```json
{
  "readings": [
    {
      "deviceId": "device_001",
      "timestamp": "2024-02-28T10:30:00Z",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "level": 4,
      "rsrp": -95,
      "networkType": "LTE"
    },
    {
      "deviceId": "device_002",
      "timestamp": "2024-02-28T10:31:00Z",
      "latitude": 40.7150,
      "longitude": -74.0070,
      "level": 3,
      "rsrp": -100,
      "networkType": "5G"
    }
  ]
}
```

**Example (curl):**
```bash
curl -X POST http://sa.agentraeg.com/api/network-data/batch \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [
      {
        "deviceId": "device_001",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "level": 4,
        "rsrp": -95,
        "networkType": "LTE"
      },
      {
        "deviceId": "device_002",
        "latitude": 40.7150,
        "longitude": -74.0070,
        "level": 3,
        "rsrp": -100,
        "networkType": "5G"
      }
    ]
  }'
```

**Response:**
```json
{
  "total_submitted": 2,
  "successful": 2,
  "failed": 0,
  "details": [
    {
      "index": 0,
      "device_id": "device_001",
      "status": "success",
      "id": 1
    },
    {
      "index": 1,
      "device_id": "device_002",
      "status": "success",
      "id": 2
    }
  ]
}
```

---

## GET Methods

### 1. Get Device Readings
**GET** `/api/network-data/{device_id}`

Retrieve all readings for a specific device.

**Query Parameters:**
- `limit` (integer, default: 100): Maximum results per page (max 1000)
- `offset` (integer, default: 0): Number of results to skip for pagination

**Example (curl):**
```bash
# Get latest 50 readings for device_001
curl -X GET "http://sa.agentraeg.com/api/network-data/device_001?limit=50&offset=0"

# Get readings with pagination
curl -X GET "http://sa.agentraeg.com/api/network-data/device_001?limit=100&offset=100"
```

**Response:**
```json
[
  {
    "id": 1,
    "device_id": "device_001",
    "timestamp": "2024-02-28T10:30:00+00:00",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "level": 4,
    "asu": 20,
    "rsrp": -95,
    "rssi": -65,
    "dbm": -95,
    "rsrq": 15,
    "network_type": "LTE",
    "operator": "AT&T",
    "cell_id": "12345678",
    "physical_cell_id": 123,
    "tracking_area_code": 456,
    "created_at": "2024-02-28T10:30:00.123456+00:00"
  }
]
```

---

### 2. Get All Devices
**GET** `/api/devices`

Retrieve a list of all devices with their statistics.

**Example (curl):**
```bash
curl -X GET http://sa.agentraeg.com/api/devices
```

**Response:**
```json
[
  {
    "device_id": "device_001",
    "last_reading": "2024-02-28T10:30:00+00:00",
    "reading_count": 45
  },
  {
    "device_id": "device_002",
    "last_reading": "2024-02-28T10:31:00+00:00",
    "reading_count": 32
  }
]
```

---

## Error Handling

Common HTTP status codes:
- **200**: Success
- **400**: Bad request (invalid timestamp format, validation error)
- **500**: Internal server error
- **503**: Database connection failed

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```