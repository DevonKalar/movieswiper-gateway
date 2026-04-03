# ms-gateway

API gateway for the movie-swiper platform. Handles authentication, rate limiting, request logging, CORS, and reverse-proxying to downstream microservices.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

## Setup

```bash
poetry install
cp .env.example .env
# edit .env — JWT_SECRET is required
```

## Running

```bash
make dev      # hot-reload dev server on :8000
make start    # production server
```

## Development

```bash
make test     # run test suite
make lint     # ruff check
make fmt      # ruff format
make check    # lint + test
```

## Configuration

All config is via environment variables (or `.env`). See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | — | **Required.** Secret used to verify HS256 tokens |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_AUDIENCE` | — | Expected `aud` claim (omit to skip check) |
| `JWT_ISSUER` | — | Expected `iss` claim (omit to skip check) |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins as a JSON array |
| `RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit per client IP |
| `DOWNSTREAM_TIMEOUT_SECONDS` | `10.0` | Per-request timeout for upstream calls |
| `DOWNSTREAM_MAX_RETRIES` | `3` | Max retry attempts on timeout/connect errors |
| `DOWNSTREAM_RETRY_BACKOFF` | `0.5` | Exponential backoff base (seconds) |
| `SERVICES__{name}` | — | Route prefix → upstream base URL (see below) |

## Service routing

Add a downstream service by setting `SERVICES__{prefix}=http://host:port`:

```env
SERVICES__movies=http://movies-service:8000
SERVICES__users=http://users-service:8001
```

Requests are matched by longest prefix. `/movies/trending` proxies to `http://movies-service:8000/trending`.

## Request flow

```
Client
  └─ CORS
      └─ Rate limiter (slowapi, keyed on client IP)
          └─ Logging middleware (injects X-Request-ID)
              └─ JWT validation (bearer token → claims)
                  └─ Proxy route
                      └─ Downstream service (httpx + tenacity retries)
```

JWT claims are not re-validated by downstream services — the gateway forwards the verified subject as `X-User-ID`. `GET /health` bypasses JWT validation.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | No | Liveness check |
| `*` | `/{path}` | Bearer JWT | Proxy to configured upstream |
