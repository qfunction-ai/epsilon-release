"""Security event endpoints.

Proxies to LettaLocal's security events API, scoped to the calling
user. Supports filtering by event_type.

VULN-002 fix (security review 2026-08-29): the free-form agent_id
query parameter was removed — it was forwarded to LettaLocal without
any ownership check, letting any authenticated user read other users'
agent events. The feed is now scoped server-side to the caller's own
agents (resolved from their session rows). Attributed events
(agent_id present) are only shown for agents the caller owns;
unattributed system-level events are shown to all authenticated
users — attribution is the disclosure boundary. The frontend never
sent agent_id, so no caller breaks; unknown query params are ignored
by FastAPI, so stale callers degrade to the scoped feed.
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


@router.get("/events")
async def get_security_events(
    request: Request,
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Proxy to LettaLocal security events, scoped to the calling user.

    Fetches the requested limit from LettaLocal, then filters to the
    caller's agents — the scoped result may be shorter than the limit.
    Acceptable at teaching scale.
    """
    letta_client = request.app.state.letta_client

    # Caller's agent set: session rows for this user. agent_id is None
    # (in-code sentinel before first agent creation, agent.py
    # "Ensure None, not empty string") or "" defensively — drop both.
    result = await db.execute(
        select(SessionModel.agent_id).where(SessionModel.user_id == user.id)
    )
    agent_ids = {aid for aid in result.scalars() if aid}

    events = await letta_client.get_security_events(
        event_type=event_type,
        limit=limit,
    )
    scoped = [
        e for e in events if not e.get("agent_id") or e.get("agent_id") in agent_ids
    ]
    return {"events": scoped}
