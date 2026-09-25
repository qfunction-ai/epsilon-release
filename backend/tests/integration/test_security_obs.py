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
    # Mapped shape (task #2): unattributed events survive, normalized
    assert len(events) == 1
    assert events[0]["event_type"] == "server_notice"
    assert events[0]["agent_id"] is None
    assert events[0]["tool_name"] == ""


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


# ---------------------------------------------------------------------------
# Task #2: mapping layer + scoped row proxies
# ---------------------------------------------------------------------------

def test_events_mapped_to_frontend_shape(app_client):
    """The mapping layer normalizes LettaLocal's nested shape to the
    flat frontend type: created_at -> timestamp, event_data fields ->
    top-level, label extracted, and the vuln_id JOIN populated from
    the caller's session rows (the column was empty before task #2)."""
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    agent = _run_agent(c, h, vuln="llm05_data_poisoning")

    stub.security_events = [
        {
            "id": "sevt-1",
            "created_at": "2026-09-25T19:00:00Z",
            "event_type": "injection_detected",
            "agent_id": agent,
            "run_id": "run-1",
            "step_id": "step-1",
            "event_data": {
                "tool_name": "archival_memory_search",
                "label": "instruction_override",
                "reason": "instruction_override",
            },
        },
        {
            "id": "sevt-2",
            "created_at": "2026-09-25T19:01:00Z",
            "event_type": "message_sent",
            "agent_id": agent,
            "run_id": "run-1",
            "event_data": {"agent_id": agent},
        },
        {
            "id": "sevt-3",
            "created_at": "2026-09-25T19:02:00Z",
            "event_type": "tool_denied",
            "agent_id": None,
            "event_data": {
                "tool_name": "execute_code",
                "reason": "Tool 'execute_code' is in denied_tools list",
            },
        },
    ]

    r = c.get("/security/events", headers=h)
    assert r.status_code == 200
    events = {e["id"]: e for e in r.json()["events"]}

    inj = events["sevt-1"]
    assert inj["timestamp"] == "2026-09-25T19:00:00Z"
    assert inj["tool_name"] == "archival_memory_search"
    assert inj["label"] == "instruction_override"
    assert inj["run_id"] == "run-1" and inj["step_id"] == "step-1"
    assert inj["vuln_id"] == "2026_llm05_data_poisoning", "vuln_id join missing"

    msg = events["sevt-2"]
    assert msg["tool_name"] == "", "message_sent null tool must map to empty, not undefined"
    assert "tool_name" in msg and msg["tool_name"] is not None

    denied = events["sevt-3"]
    assert denied["vuln_id"] is None, "unattributed events carry no vuln_id"
    assert denied["reason"].startswith("Tool 'execute_code'")


def test_events_filters_survive_mapping(app_client):
    """event_type and limit pass through the mapping to the proxy."""
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    r = c.get("/security/events", headers=h, params={"event_type": "injection_detected", "limit": 5})
    assert r.status_code == 200
    call = next(kw for name, kw in stub.calls if name == "get_security_events")
    assert call.get("event_type") == "injection_detected"
    assert call.get("limit") == 5


def test_tool_calls_scoped_to_user(app_client):
    """Row scoping: tool-call records for another user's agents never
    appear, same disclosure boundary as events."""
    c, stub = app_client.client, app_client.stub
    h_a = _auth(c)
    agent_a = _run_agent(c, h_a)
    _sql_second_user("studentC")
    h_b = _login(c, "studentC")
    agent_b = _run_agent(c, h_b, vuln="llm02_sensitive_info")

    stub.tool_calls = [
        {"id": "tc-1", "tool_name": "archival_memory_search", "agent_id": agent_a, "success": True},
        {"id": "tc-2", "tool_name": "file_read", "agent_id": agent_b, "success": True},
        {"id": "tc-3", "tool_name": "execute_code", "agent_id": None, "success": False},
    ]
    r = c.get("/observability/tool-calls", headers=h_a)
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()["tool_calls"]]
    assert "tc-2" not in ids, "other user's tool call leaked"
    # Unattributed rows (agent_id None) are dropped for rows: unlike
    # system events, a tool call with no agent is not a disclosure
    # surface, and the distribution would double-count.
    assert ids == ["tc-1"]


def test_runs_scoped_with_vuln_join(app_client):
    """Runs scoped to the caller; vuln_id joined; security_flags in
    metadata pass through (the durable badge record)."""
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    agent = _run_agent(c, h, vuln="llm05_data_poisoning")
    _sql_second_user("studentD")
    h_b = _login(c, "studentD")
    agent_b = _run_agent(c, h_b, vuln="llm03_excessive_agency")

    stub.runs = [
        {
            "id": "run-1", "agent_id": agent, "status": "completed",
            "stop_reason": "end_turn",
            "metadata": {"security_flags": [{"flag": "instruction_override"}]},
            "created_at": "2026-09-25T19:00:00Z",
        },
        {"id": "run-2", "agent_id": agent_b, "status": "completed"},
    ]
    r = c.get("/observability/runs", headers=h)
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert [x["id"] for x in runs] == ["run-1"]
    assert runs[0]["vuln_id"] == "2026_llm05_data_poisoning"
    assert runs[0]["metadata"]["security_flags"][0]["flag"] == "instruction_override"


def test_row_proxies_require_auth(app_client):
    c = app_client.client
    assert c.get("/observability/tool-calls").status_code == 401
    assert c.get("/observability/runs").status_code == 401
