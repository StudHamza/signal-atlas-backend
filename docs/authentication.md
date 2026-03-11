# Authentication

All endpoints (except `GET /`) require an API key passed in the `X-API-Key` request header.

## Configuring keys

Set the `API_KEYS` environment variable to a comma-separated list of valid keys:

```env
API_KEYS=key-one,key-two,key-three
```

If `API_KEYS` is not set, the server generates a random key at startup and logs it as a warning — useful for local development, not for production.

## Example request

```bash
curl -H "X-API-Key: your-key" https://your-domain.com/health
```

## Error responses

| Status | Meaning |
|--------|---------|
| `401`  | Key missing or not recognised |