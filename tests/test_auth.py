import time

import pytest


# ---------------------------------------------------------------------------
# Protected routes
# ---------------------------------------------------------------------------

async def test_missing_auth_header_returns_401(client):
    response = await client.get("/movies/trending")

    assert response.status_code == 401


async def test_invalid_token_returns_401(client):
    response = await client.get(
        "/movies/trending",
        headers={"Authorization": "Bearer this.is.garbage"},
    )

    assert response.status_code == 401


async def test_wrong_secret_returns_401(client, make_token):
    token = make_token(secret="wrong-secret")
    response = await client.get(
        "/movies/trending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


async def test_expired_token_returns_401(client, make_token):
    token = make_token({"sub": "user-123", "exp": int(time.time()) - 60})
    response = await client.get(
        "/movies/trending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


async def test_valid_token_is_accepted(client, auth_headers):
    response = await client.get("/movies/trending", headers=auth_headers)

    assert response.status_code == 200


async def test_token_without_sub_returns_401(client, make_token):
    token = make_token({"sub": None})
    response = await client.get(
        "/movies/trending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/auth/login", "/auth/register", "/auth/refresh"])
async def test_public_route_requires_no_token(client, path):
    response = await client.post(path, json={})

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/auth/login", "/auth/register", "/auth/refresh"])
async def test_public_route_does_not_forward_x_user_id(client, mock_proxy_client, path):
    await client.post(path, json={})

    forwarded = mock_proxy_client.forward.call_args.kwargs["headers"]
    assert "X-User-ID" not in forwarded


async def test_public_route_accepts_token_if_provided(client, auth_headers):
    """A valid token on a public route should not cause a rejection."""
    response = await client.post("/auth/login", json={}, headers=auth_headers)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Header spoofing
# ---------------------------------------------------------------------------

async def test_client_supplied_x_user_id_is_stripped(client, mock_proxy_client, auth_headers):
    """A client must not be able to spoof X-User-ID; the gateway peels it and re-sets it from the JWT."""
    spoofed_headers = {**auth_headers, "X-User-ID": "evil-user-999"}
    await client.get("/movies/trending", headers=spoofed_headers)

    forwarded = mock_proxy_client.forward.call_args.kwargs["headers"]
    assert forwarded.get("X-User-ID") == "user-123"


async def test_client_supplied_x_user_id_stripped_on_public_route(client, mock_proxy_client):
    """X-User-ID from the client is dropped even on public (unauthenticated) routes."""
    await client.post("/auth/login", json={}, headers={"X-User-ID": "evil-user-999"})

    forwarded = mock_proxy_client.forward.call_args.kwargs["headers"]
    assert "X-User-ID" not in forwarded
