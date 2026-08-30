"""Observability endpoints.

Proxies to LettaLocal's observability API for run counts, token totals,
tool call distribution, and security event summaries.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview")
async def get_observability(
    request: Request,
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    user: User = Depends(get_current_user),
):
    """Proxy to LettaLocal observability overview."""
    letta_client = request.app.state.letta_client
    return await letta_client.get_observability(agent_id=agent_id)
