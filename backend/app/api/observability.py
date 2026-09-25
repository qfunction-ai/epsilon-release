"""Observability endpoints.

Proxies to LettaLocal's observability API for run counts, token totals,
tool call distribution, and security event summaries.

VULN-002 fix (security review 2026-08-29): the free-form agent_id
query parameter was removed — it was forwarded to LettaLocal without
any ownership check. The frontend never sent it.

DELIBERATE LIMITATION — the overview is a deployment-wide aggregate.
LettaLocal returns pure counts (total_runs, token totals, tool calls,
security events) with no per-agent rows, so cross-user scoping here
would require one overview request per agent plus a merge. That was
considered and rejected: avg_step_ms cannot be merged correctly
without step-count weights, and Epsilon's single-user deployment
posture (registration closes after the first user; see README) does
not justify N requests per page load. In the default deployment this
aggregate IS the caller's own data. If multi-user deployments ever
become supported, the right fix is a LettaLocal-side multi-agent
filter parameter, not a backend fan-out.

ROW endpoints (2026-09-25, task #2) — tool-calls and runs carry
agent_id per row, so both are scoped to the caller's agent set exactly
like the security events feed (same reused session query; the
aggregate-only posture above does NOT extend to row data — a scoped
events feed next to unscoped adjacent tables is the inconsistency the
reviews catch). The runs list also serves as the durable companion to
the live chat badge: run metadata carries security_flags since
LettaLocal 0.16.32, closing the documented live-vs-history seam.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview")
async def get_observability(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Proxy to LettaLocal observability overview (deployment-wide aggregate)."""
    letta_client = request.app.state.letta_client
    return await letta_client.get_observability()


@router.get("/tool-calls")
async def get_tool_calls(
    request: Request,
    limit: int = Query(100, ge=1, le=500, description="Max tool call records"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent tool calls, scoped to the caller's agents.

    Records carry tool_name, duration_ms, success/error, tool_args,
    and a truncated tool_result. Ordered newest-first by the fork.
    """
    letta_client = request.app.state.letta_client
    result = await db.execute(
        select(SessionModel.agent_id).where(SessionModel.user_id == user.id)
    )
    agent_ids = {aid for aid in result.scalars() if aid}

    calls = await letta_client.list_tool_calls(limit=limit)
    return {"tool_calls": [c for c in calls if c.get("agent_id") in agent_ids]}


@router.get("/runs")
async def get_recent_runs(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Max run records"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent runs, scoped to the caller's agents.

    Run metadata may carry security_flags (0.16.32+) — the durable
    record the live chat badge defers to.
    """
    letta_client = request.app.state.letta_client
    result = await db.execute(
        select(SessionModel.agent_id, SessionModel.vulnerability_id).where(
            SessionModel.user_id == user.id
        )
    )
    owned = [(aid, vid) for aid, vid in result.all() if aid]
    agent_ids = {aid for aid, _ in owned}
    vuln_by_agent = {aid: vid for aid, vid in owned}

    runs = await letta_client.list_runs(limit=limit * 5)
    scoped = []
    for r in runs:
        if r.get("agent_id") in agent_ids:
            r = dict(r)
            r["vuln_id"] = vuln_by_agent.get(r.get("agent_id"))
            scoped.append(r)
        if len(scoped) >= limit:
            break
    return {"runs": scoped}
