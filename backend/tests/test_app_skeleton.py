"""Step 0 checks: the app starts, health answers in the contract shape, docs are served.
Uses the throwaway database configured in conftest.py.
"""


def test_health_shape(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"status", "trading_day", "db"}
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["trading_day"] is None or len(body["trading_day"]) == 10


def test_docs_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "AI Trade Assistant API"


def test_cors_allows_frontend(client):
    r = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
