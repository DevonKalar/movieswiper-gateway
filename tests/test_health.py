async def test_health_returns_ok(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_requires_no_auth(client):
    """Health endpoint must be reachable without a token."""
    response = await client.get("/health")

    assert response.status_code == 200
