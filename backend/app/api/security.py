"""Security event endpoints.

Proxies to LettaLocal's security events API. Supports filtering by
agent_id and event_type.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events")
async def get_security_events(
    request: Request,
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    user: User = Depends(get_current_user),
):
    """Proxy to LettaLocal security events."""
    letta_client = request.app.state.letta_client
    events = await letta_client.get_security_events(
        agent_id=agent_id,
        event_type=event_type,
        limit=limit,
    )
    return {"events": events}
