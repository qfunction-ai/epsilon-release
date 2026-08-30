"""Security-events and observability proxy integration (stubbed letta)."""
from __future__ import annotations


def _auth(client):
    client.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    r = client.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_security_events_proxy(app_client):
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    r = c.get("/security/events", headers=h, params={"agent_id": "agent-x"})
    assert r.status_code == 200
    assert r.json()["events"]
    assert any(call[0] == "get_security_events" for call in stub.calls)


def test_observability_proxy(app_client):
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    r = c.get("/observability/overview", headers=h)
    assert r.status_code == 200
    assert any(call[0] == "get_observability" for call in stub.calls)


def test_proxies_require_auth(app_client):
    c = app_client.client
    assert c.get("/security/events").status_code == 401
    assert c.get("/observability/overview").status_code == 401
