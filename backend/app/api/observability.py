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
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.api.auth import get_current_user
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
