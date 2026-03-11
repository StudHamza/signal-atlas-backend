# System Endpoints

## `GET /`

Ping endpoint. No authentication required.

**Response**

```json
{
  "message": "Network Monitor API is running!",
  "status": "OK",
  "version": "2.0.0"
}
```

---

## `GET /health`

Deep health check. Verifies the database connection.

**Auth required:** Yes

**Response `200`**

```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-06-01T12:00:00.000000"
}
```

**Response `503`** — database unreachable

```json
{ "detail": "Database connection failed" }
```