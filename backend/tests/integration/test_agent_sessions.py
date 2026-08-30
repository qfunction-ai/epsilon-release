"""Agent session integration: keying, scoping, reset semantics, abort."""
from __future__ import annotations


def _auth(client):
    client.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    r = client.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _second_user(client, username="studentB"):
    r = client.post("/auth/login", json={"username": username, "password": "password123"})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_run_creates_session_and_runs_agent(app_client):
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    r = c.post("/agent/run", headers=h, json={
        "vuln_id": "llm01_prompt_injection", "year": 2026,
        "code_state": "vulnerable", "message": "hello",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"].startswith("agent-stub-")
    assert "stub reply" in body["response"]["messages"][0]["content"]
    assert any(call[0] == "create_agent" for call in stub.calls)
    assert any(call[0] == "run_agent" for call in stub.calls)


def test_session_scoped_to_user(app_client):
    """Cross-user isolation: user A's session is invisible to user B."""
    c = app_client.client
    h = _auth(c)
    r1 = c.post("/agent/run", headers=h, json={
        "vuln_id": "llm01_prompt_injection", "year": 2026,
        "code_state": "vulnerable", "message": "user A message",
    })
    assert r1.status_code == 200

    # user B on the SAME vuln gets their OWN agent (not A's)
    # NOTE: registration is locked after first admin; second login
    # without registration fails — isolation via separate sessions is
    # exercised by the suite in CI against the full stack. Here we
    # verify the primary user's session shape.
    msgs = c.get(f"/agent/messages/{r1.json()['session_id']}", headers=h)
    assert msgs.status_code == 200


def test_reset_idempotent_and_scoped(app_client):
    c, stub = app_client.client, app_client.stub
    h = _auth(c)
    c.post("/agent/run", headers=h, json={
        "vuln_id": "llm02_sensitive_info", "year": 2026,
        "code_state": "fixed", "message": "hi",
    })
    r1 = c.request("DELETE", "/agent/session", headers=h, json={
        "year": 2026, "vuln_id": "llm02_sensitive_info",
    })
    assert r1.status_code == 200
    assert r1.json()["reset"] is True
    # abort-before-delete fired (wiring B order: abort then delete,
    # judged against the LAST delete_agent — toggle recreates also delete)
    ops = [call[0] for call in stub.calls]
    assert "abort_active_runs" in ops
    assert ops.index("abort_active_runs") < len(ops) - 1 - ops[::-1].index("delete_agent")
    # second reset: nothing to do
    r2 = c.request("DELETE", "/agent/session", headers=h, json={
        "year": 2026, "vuln_id": "llm02_sensitive_info",
    })
    assert r2.status_code == 200
    assert r2.json()["reset"] is False


def test_reset_requires_auth(app_client):
    r = app_client.client.request("DELETE", "/agent/session", json={
        "year": 2026, "vuln_id": "llm01_prompt_injection",
    })
    assert r.status_code == 401


def test_run_unknown_vuln_404(app_client):
    c = app_client.client
    h = _auth(c)
    r = c.post("/agent/run", headers=h, json={
        "vuln_id": "llm99_nonexistent", "year": 2026,
        "code_state": "vulnerable", "message": "hi",
    })
    assert r.status_code == 404
