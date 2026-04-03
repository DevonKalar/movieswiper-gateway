# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
poetry install

# Run dev server (reload on change)
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest

# Run a single test file
poetry run pytest tests/path/to/test_file.py

# Lint
poetry run ruff check .

# Format
poetry run ruff format .
```

## Architecture

`ms-gateway` is an API gateway that sits in front of all downstream movie-swiper microservices. Every inbound request (except `GET /health`) goes through the full middleware stack before being proxied.

### Request lifecycle

```
Client → CORS → Rate limiter → Logging middleware → JWT validation → Proxy route → Downstream service
```

1. **CORS** — `CORSMiddleware` applied at the ASGI layer.
2. **Rate limiting** — `slowapi` keyed on client IP; default limit configured via `RATE_LIMIT_DEFAULT`.
3. **Logging** — `app/middleware/logging.py` injects a `X-Request-ID` UUID and logs structured JSON for every request/response pair.
4. **JWT validation** — `app/auth/jwt.py` is a FastAPI dependency (`get_current_claims`) on the proxy catch-all route. It decodes the bearer token with `python-jose` and raises 401 on failure. Verified claims are forwarded downstream as `X-User-ID`.
5. **Proxy** — `app/routes/proxy.py` resolves the request path to a downstream URL via longest-prefix match against `settings.services`, then calls `ProxyClient.forward()`.
6. **HTTP client** — `app/proxy/client.py` uses `httpx.AsyncClient` with configurable timeout. `tenacity` retries on `TimeoutException` / `ConnectError` with exponential backoff.

### Service routing

Map path prefixes to base URLs via environment variables:

```
SERVICES__movies=http://movies-service:8000
SERVICES__users=http://users-service:8001
```

`/movies/trending` → `http://movies-service:8000/trending`. Longest-prefix match wins when prefixes overlap.

### Configuration

All settings live in `app/config.py` (`pydantic-settings`). Copy `.env.example` to `.env` and set `JWT_SECRET` at minimum.

### Key design decisions

- The `GET /health` route is registered before the proxy catch-all and has no auth dependency, so it is always reachable.
- Hop-by-hop headers (defined in `app/proxy/client.py:HOP_BY_HOP`) are stripped from both forwarded requests and upstream responses.
- The `ProxyClient` is created once at startup (via `lifespan`) and stored on `app.state`, so the underlying `httpx` connection pool is shared across requests.
- `get_settings()` is `@lru_cache`-wrapped — tests that need custom settings should call `get_settings.cache_clear()` after monkeypatching.
