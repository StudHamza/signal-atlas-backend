# Coverage Request Endpoints

Coverage requests allow users to create "bounties" for network coverage data collection in a specific geographic area. A background worker processes incoming device readings and automatically scores each request.

---

## `GET /coverage-requests`

List all coverage requests with optional filters and sorting.

**Auth required:** No

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `OPEN`, `COMPLETED`, `CANCELLED` |
| `country` | string | Filter by country code (e.g. `GB`) |
| `city` | string | Filter by city name |
| `sort_by` | `reward_asc` \| `reward_desc` \| `created_at_desc` | Sort order (default: created ascending) |

### Response `200`

```json
{
  "requests": [
    {
      "id": 1,
      "title": "Downtown London Coverage",
      "description": "Need better coverage in central London",
      "country": "GB",
      "city": "London",
      "reward_amount": 100.0,
      "initial_density_score": 12.5,
      "current_density_score": 12.5,
      "target_density_score": 50.0,
      "progress_percentage": 25.0,
      "status": "OPEN",
      "created_at": "2025-05-16T10:00:00",
      "completed_at": null
    }
  ]
}
```

---

## `GET /coverage-requests/nearby`

Find coverage requests whose polygon areas are within a given radius of a point.

**Auth required:** No

Requires PostGIS (`ST_DWithin`).

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | float | ✅ | Latitude of the centre point |
| `longitude` | float | ✅ | Longitude of the centre point |
| `radius_km` | float | — | Search radius in kilometres (default: `5`) |
| `status` | string | — | Filter by status (default: `OPEN`) |
| `country` | string | — | Filter by country code |
| `city` | string | — | Filter by city name |

### Response `200`

Same structure as `GET /coverage-requests`.

---

## `GET /coverage-requests/{request_id}`

Get a single coverage request with its area as GeoJSON, contributor count, and progress percentage.

**Auth required:** No

### Response `200`

```json
{
  "id": 1,
  "title": "Downtown London Coverage",
  "description": "Need better coverage in central London",
  "country": "GB",
  "city": "London",
  "area": {
    "type": "Polygon",
    "coordinates": [[
      [-0.13, 51.50],
      [-0.12, 51.50],
      [-0.12, 51.51],
      [-0.13, 51.51],
      [-0.13, 51.50]
    ]]
  },
  "reward_amount": 100.0,
  "initial_density_score": 12.5,
  "current_density_score": 12.5,
  "target_density_score": 50.0,
  "progress_percentage": 25.0,
  "status": "OPEN",
  "contributors_count": 0,
  "created_by": "user-123",
  "created_at": "2025-05-16T10:00:00",
  "completed_at": null
}
```

### Response `404`

```json
{ "detail": "Coverage request not found" }
```

---

## `POST /coverage-requests`

Create a new coverage request.

**Auth required:** No

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | ✅ | Short title for the request |
| `description` | string | — | Optional description |
| `country` | string | ✅ | Country code (e.g. `GB`) |
| `city` | string | ✅ | City name |
| `reward_amount` | float | ✅ | Reward amount for completion |
| `target_density_score` | float | ✅ | Density score target for completion |
| `area` | object | ✅ | GeoJSON Polygon geometry |
| `created_by` | string | ✅ | User identifier |

The `area` field must be a valid GeoJSON Polygon with at least 3 distinct points:

```json
{
  "type": "Polygon",
  "coordinates": [[
    [-0.13, 51.50],
    [-0.12, 51.50],
    [-0.12, 51.51],
    [-0.13, 51.51],
    [-0.13, 51.50]
  ]]
}
```

### Response `200`

```json
{
  "message": "Coverage request created successfully",
  "request_id": 1,
  "initial_density_score": 12.5,
  "status": "OPEN"
}
```

### Response `400`

```json
{ "detail": "Invalid polygon geometry" }
```

---

## `PATCH /coverage-requests/{request_id}`

Update a coverage request. Only `OPEN` or `CANCELLED` requests can be edited (not `COMPLETED`).

**Auth required:** No

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | New title |
| `description` | string | New description |
| `reward_amount` | float | New reward (can only decrease if no contributions exist) |
| `target_density_score` | float | New target (cannot be lower than current score) |
| `status` | `OPEN` \| `CANCELLED` | Change request status |

### Response `200`

```json
{ "message": "Coverage request updated successfully" }
```

### Response `400`

```json
{ "detail": "Completed requests cannot be edited" }
```

---

## `GET /coverage-requests/{request_id}/progress`

Get progress statistics for a coverage request.

**Auth required:** No

### Response `200`

```json
{
  "request_id": 1,
  "current_density_score": 12.5,
  "target_density_score": 50.0,
  "progress_percentage": 25.0,
  "contributors_count": 3,
  "total_valid_readings": 1250,
  "status": "OPEN"
}
```

---

## `GET /coverage-requests/{request_id}/contributions`

List all contributors for a request, sorted by density contribution descending.

**Auth required:** No

### Response `200`

```json
{
  "request_id": 1,
  "contributors": [
    {
      "device_id": "device-001",
      "total_readings": 450,
      "density_contribution": 3.5,
      "reward_share": 35.0
    },
    {
      "device_id": "device-002",
      "total_readings": 200,
      "density_contribution": 1.8,
      "reward_share": 18.0
    }
  ]
}
```
