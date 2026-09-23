async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()


async def test_health_reports_database_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
