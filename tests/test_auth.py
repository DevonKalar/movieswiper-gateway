import time


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
