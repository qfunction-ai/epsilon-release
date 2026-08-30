"""Security-events and observability proxy integration (stubbed letta).

Covers the VULN-002 fix: the events feed is scoped server-side to the
calling user's agents (attribution is the disclosure boundary), and
the agent_id query parameter no longer exists.
"""
from __future__ import annotations

import asyncio

import asyncpg

TEST_DB = "postgresql://epsilon:epsilon@localhost:5432/epsilon_test"


def _auth(client, username="firstadmin"):
    client.post("/auth/register", json={
        "username": username, "password": "password123",
        "confirm_password": "password123",
    })
    r = client.post("/auth/login", json={"username": username, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sql_second_user(username="studentB"):
    """Registration closes after the first user — provision a second
    user directly via SQL (same bcrypt scheme as the auth module)."""
    from app.api.auth import hash_password

    async def _run():
        conn = await asyncpg.connect(TEST_DB)
        try:
            await conn.execute(
                "INSERT INTO users (username, hashed_password) VALUES ($1, $2)",
                username, hash_password("password123"),
            )
        finally:
            await conn.close()

    asyncio.run(_run())
    return username


def _login(client, username):
    r = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert r.status_code == 200, f"login failed for {username}: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _run_agent(client, headers, vuln="llm01_prompt_injection"):
    r = client.post("/agent/run", headers=headers, json={
        "vuln_id": vuln, "year": 2026,
        "code_state": "vulnerable", "message": "seed session",
    })
    assert r.status_code == 200, r.text
    return r.json()["agent_id"]


def test_security_events_proxy(app_client):
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    r = c.get("/security/events", headers=h)
    assert r.status_code == 200
    assert r.json()["events"]
    assert any(call[0] == "get_security_events" for call in stub.calls)


def test_events_scoped_to_user(app_client):
    """VULN-002: user A sees only their own agents' events plus
    unattributed system events — never user B's attributed events."""
    c, stub = app_client.client, app_client.stub
    h_a = _auth(c)
    agent_a = _run_agent(c, h_a)

    _sql_second_user("studentB")
    h_b = _login(c, "studentB")
    agent_b = _run_agent(c, h_b, vuln="llm02_sensitive_info")

    stub.security_events = [
        {"event_type": "tool_denied", "agent_id": agent_a},
        {"event_type": "canary_hit", "agent_id": agent_b},
        {"event_type": "server_notice", "agent_id": None},
    ]

    r = c.get("/security/events", headers=h_a)
    assert r.status_code == 200
    events = r.json()["events"]
    agent_ids = {e.get("agent_id") for e in events}
    assert agent_b not in agent_ids, "user B's agent leaked into A's feed"
    assert agent_a in agent_ids
    assert None in agent_ids, "unattributed system events must stay visible"

    r = c.get("/security/events", headers=h_b)
    assert r.status_code == 200
    agent_ids = {e.get("agent_id") for e in r.json()["events"]}
    assert agent_a not in agent_ids, "user A's agent leaked into B's feed"
    assert agent_b in agent_ids


def test_events_scoped_requires_session_row(app_client):
    """VULN-002: a user with no sessions (empty agent set) sees only
    unattributed events."""
    c, stub = app_client.client, app_client.stub
    h = _auth(c)

    stub.security_events = [
        {"event_type": "tool_denied", "agent_id": "agent-someone-else"},
        {"event_type": "server_notice", "agent_id": None},
    ]
    r = c.get("/security/events", headers=h)
    assert r.status_code == 200
    events = r.json()["events"]
    assert events == [{"event_type": "server_notice", "agent_id": None}]


def test_unknown_query_params_ignored(app_client):
    """VULN-002: the agent_id param no longer exists. Stale callers
    passing it get the scoped feed — not a 422, not a leak."""
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    stub.security_events = [
        {"event_type": "tool_denied", "agent_id": "agent-not-mine"},
        {"event_type": "server_notice", "agent_id": None},
    ]
    r = c.get("/security/events", headers=h, params={"agent_id": "agent-not-mine"})
    assert r.status_code == 200
    agent_ids = {e.get("agent_id") for e in r.json()["events"]}
    assert "agent-not-mine" not in agent_ids


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
