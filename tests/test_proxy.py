import json

import httpx
import pytest


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

async def test_request_forwarded_to_correct_upstream(client, auth_headers, mock_proxy_client):
    await client.get("/movies/trending", headers=auth_headers)

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert kwargs["url"] == "http://movies-service/trending"


async def test_request_method_preserved(client, auth_headers, mock_proxy_client):
    await client.post("/movies/reviews", json={}, headers=auth_headers)

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert kwargs["method"] == "POST"


async def test_query_params_forwarded(client, auth_headers, mock_proxy_client):
    await client.get("/movies/search?q=inception&page=2", headers=auth_headers)

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert kwargs["params"] == {"q": "inception", "page": "2"}


async def test_request_body_forwarded(client, auth_headers, mock_proxy_client):
    payload = {"rating": 5, "comment": "great"}
    await client.post("/movies/reviews", json=payload, headers=auth_headers)

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert json.loads(kwargs["content"]) == payload


async def test_no_service_for_path_returns_404(client, auth_headers):
    response = await client.get("/unknown/path", headers=auth_headers)

    assert response.status_code == 404


async def test_longest_prefix_wins(client, auth_headers, mock_proxy_client):
    """
    /users/profile should map to the users service, not be swallowed by
    a shorter prefix if one existed. Verify the remainder path is correct.
    """
    await client.get("/users/profile", headers=auth_headers)

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert kwargs["url"] == "http://users-service/profile"


# ---------------------------------------------------------------------------
# Response passthrough
# ---------------------------------------------------------------------------

async def test_upstream_status_code_proxied(client, auth_headers, mock_proxy_client):
    mock_proxy_client.forward.return_value = httpx.Response(404, content=b"not found")

    response = await client.get("/movies/999", headers=auth_headers)

    assert response.status_code == 404


async def test_upstream_body_proxied(client, auth_headers, mock_proxy_client):
    mock_proxy_client.forward.return_value = httpx.Response(
        200,
        json={"title": "Inception"},
        headers={"content-type": "application/json"},
    )

    response = await client.get("/movies/1", headers=auth_headers)

    assert response.json() == {"title": "Inception"}


async def test_upstream_5xx_proxied_without_error(client, auth_headers, mock_proxy_client):
    """Non-2xx upstream responses are passed through, not converted to gateway errors."""
    mock_proxy_client.forward.return_value = httpx.Response(503, content=b"unavailable")

    response = await client.get("/movies/1", headers=auth_headers)

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_timeout_returns_504(client, auth_headers, mock_proxy_client):
    mock_proxy_client.forward.side_effect = httpx.ReadTimeout("timed out")

    response = await client.get("/movies/slow", headers=auth_headers)

    assert response.status_code == 504


async def test_connect_error_returns_502(client, auth_headers, mock_proxy_client):
    mock_proxy_client.forward.side_effect = httpx.ConnectError("connection refused")

    response = await client.get("/movies/down", headers=auth_headers)

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

async def test_hop_by_hop_headers_not_forwarded(client, auth_headers, mock_proxy_client):
    await client.get(
        "/movies/trending",
        headers={**auth_headers, "Connection": "keep-alive"},
    )

    forwarded = {k.lower() for k in mock_proxy_client.forward.call_args.kwargs["headers"]}
    assert "connection" not in forwarded


async def test_x_user_id_set_from_jwt_sub(client, make_token, mock_proxy_client):
    token = make_token({"sub": "user-abc"})
    await client.get("/movies/trending", headers={"Authorization": f"Bearer {token}"})

    kwargs = mock_proxy_client.forward.call_args.kwargs
    assert kwargs["headers"]["X-User-ID"] == "user-abc"


async def test_x_request_id_present_in_response(client, auth_headers):
    response = await client.get("/movies/trending", headers=auth_headers)

    assert "x-request-id" in response.headers
    # Should be a UUID (36 chars with hyphens)
    assert len(response.headers["x-request-id"]) == 36


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

async def test_cors_header_returned_when_origin_sent(client, auth_headers, mock_proxy_client):
    response = await client.get(
        "/movies/trending",
        headers={**auth_headers, "Origin": "http://localhost:3000"},
    )

    assert "access-control-allow-origin" in response.headers
