async def test_client_hits_healthcheck(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
