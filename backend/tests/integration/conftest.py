"""Integration test fixtures: real DB, stubbed LettaLocal, real app.

The Delta fake-letta philosophy applied at the dependency layer
(TEST_INFRA_PLAN.md workstream C): integration tests verify BACKEND
plumbing (auth, session scoping, reset semantics, API shapes) with the
model layer faked. The live-model tiers (chips matrix, numbered E2E)
run in their own dispatch-only workflows.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import Base  # noqa: E402
from app.main import app as epsilon_app  # noqa: E402

DB_NAME = "epsilon_test"
PG_DSN_TEMPLATE = os.environ.get(
    "EPSILON_TEST_PG",
    "postgresql+asyncpg://epsilon:epsilon@localhost:5432/{db}",
)
ADMIN_DSN = os.environ.get(
    "EPSILON_TEST_ADMIN_PG",
    "postgresql://epsilon:epsilon@localhost:5432/postgres",
)


class StubLettaClient:
    """Stub of the LettaClient interface the API routes touch.

    Records every call for assertions (abort-before-delete, run
    payloads). Canned agent ids and run responses.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._next = 0

    def _id(self) -> str:
        self._next += 1
        return f"agent-stub-{self._next}"

    async def create_agent(self, config) -> str:
        self.calls.append(("create_agent", config))
        return self._id()

    async def delete_agent(self, agent_id: str) -> None:
        self.calls.append(("delete_agent", agent_id))

    async def abort_run(self, run_id: str) -> dict:
        self.calls.append(("abort_run", run_id))
        return {"id": run_id, "status": "cancelled"}

    async def abort_active_runs(self, agent_id: str) -> int:
        self.calls.append(("abort_active_runs", agent_id))
        return 0

    async def run_agent(self, agent_id: str, message: str) -> dict:
        self.calls.append(("run_agent", agent_id, message))
        return {
            "messages": [
                {
                    "id": "m1",
                    "message_type": "assistant_message",
                    "content": f"stub reply to: {message[:30]}",
                }
            ]
        }

    async def get_messages(self, agent_id: str) -> dict:
        self.calls.append(("get_messages", agent_id))
        return {"messages": [{"message_type": "assistant_message", "content": "stub history"}]}

    async def get_security_events(self, **kw) -> list:
        self.calls.append(("get_security_events", kw))
        return [{"event_type": "tool_denied", "agent_id": kw.get("agent_id")}]

    async def get_observability(self, **kw) -> dict:
        self.calls.append(("get_observability", kw))
        return {"runs": 1, "tokens": 10}

    async def ensure_tools_registered(self) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.fixture(scope="session")
def test_database():
    """Create a fresh epsilon_test database, then dispose."""
    async def _run():
        conn = await asyncpg.connect(ADMIN_DSN.replace("+asyncpg", ""))
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
            await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
        finally:
            await conn.close()
    asyncio.run(_run())
    yield f"{PG_DSN_TEMPLATE.format(db=DB_NAME)}"
    async def _drop():
        conn = await asyncpg.connect(ADMIN_DSN.replace("+asyncpg", ""))
        try:
            await conn.execute(
                f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)'
            )
        finally:
            await conn.close()
    asyncio.run(_drop())


@pytest.fixture(scope="session")
def app_session(test_database):
    """ONE TestClient for the whole session.

    The app does not survive lifespan restarts (LettaClient is a
    class-level singleton whose httpx client is closed on lifespan
    exit and never recreated — second entry gets a dead client).
    So: enter once, reset DATA per test instead of re-entering.
    """
    import app.database as database_module
    from app.config import get_settings

    get_settings.cache_clear()
    database_module._engine = None
    database_module._async_session_maker = None
    os.environ["DATABASE_URL"] = test_database

    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    from app.models.session import Session as SessionModel  # noqa: F401
    from app.models.user import User  # noqa: F401

    async def _create_schema():
        eng = _cae(test_database)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(_create_schema())

    with TestClient(epsilon_app, raise_server_exceptions=True) as client:
        stub = StubLettaClient()
        epsilon_app.state.letta_client = stub
        yield SimpleNamespace(client=client, stub=stub)


@pytest.fixture()
def app_client(app_session):
    """Per-test: clean tables (keep schema), fresh stub call log."""
    async def _truncate():
        eng = asyncpg.connect(
            __import__("app.config", fromlist=["get_settings"])
            .get_settings().DATABASE_URL.replace("+asyncpg", "")
        )
        conn = await eng
        try:
            await conn.execute("TRUNCATE users, sessions CASCADE")
        finally:
            await conn.close()

    asyncio.run(_truncate())
    app_session.stub.calls.clear()
    # The login rate limiter is module-level state in app.api.auth —
    # it survives across tests in the session-scoped app and 429s
    # every later login test once one test burns the budget.
    from app.api import auth as _auth_mod
    _auth_mod._login_attempts.clear()
    yield app_session
