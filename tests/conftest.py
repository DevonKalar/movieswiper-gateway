import os

# Provide JWT_SECRET before app modules are imported so the module-level
# `app = create_app()` in main.py does not raise a validation error.
os.environ.setdefault("JWT_SECRET", "test-secret")

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from jose import jwt  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.proxy.client import ProxyClient  # noqa: E402

TEST_JWT_SECRET = "test-secret"
TEST_MOVIES_URL = "http://movies-service"
TEST_USERS_URL = "http://users-service"


@pytest.fixture
def test_settings() -> Settings:
    """Deterministic settings for every test — no env var parsing required."""
    return Settings(
        jwt_secret=TEST_JWT_SECRET,
        services={"movies": TEST_MOVIES_URL, "users": TEST_USERS_URL},
    )


@pytest.fixture
def make_token():
    """Factory that mints signed JWTs against the test secret."""
    def _make(payload: dict | None = None, secret: str = TEST_JWT_SECRET) -> str:
        claims = {"sub": "user-123", **(payload or {})}
        return jwt.encode(claims, secret, algorithm="HS256")
    return _make


@pytest.fixture
def auth_headers(make_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture
def mock_proxy_client() -> AsyncMock:
    """AsyncMock standing in for ProxyClient with a default 200 response."""
    mock = AsyncMock(spec=ProxyClient)
    mock.forward.return_value = httpx.Response(
        200,
        content=b'{"ok": true}',
        headers={"content-type": "application/json"},
    )
    return mock


@pytest_asyncio.fixture
async def client(test_settings: Settings, mock_proxy_client: AsyncMock) -> AsyncClient:
    """
    Full ASGI test client.

    - Settings are injected via dependency_overrides so all route handlers
      see the correct JWT secret and service map without touching env vars.
    - The real ProxyClient created during lifespan is replaced with
      mock_proxy_client so no outbound HTTP calls are made.
    """
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        app.state.proxy_client = mock_proxy_client
        yield ac
