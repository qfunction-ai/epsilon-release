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

Mapping layer (2026-09-25, task #2): LettaLocal events carry the
payload nested ({event_data: {tool_name, reason/label}, created_at,
run_id, step_id}) while the frontend SecurityEvent type expects flat
{timestamp, tool_name, reason, vuln_id}. The mapping lives HERE so
there is one normalization site, testable with the integration
fixture pattern, and so the vuln_id join (agent_id -> session ->
vulnerability_id — the same rows the scoping query reads) composes
with scoping instead of duplicating it. Before this, the Vuln column
rendered empty: the frontend type carried the field but no layer ever
produced it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _map_event(event: dict[str, Any], vuln_by_agent: dict[str, str]) -> dict[str, Any]:
    """Normalize a LettaLocal security event to the frontend shape.

    - created_at -> timestamp
    - event_data.tool_name / reason / label -> top-level
    - detection label extracted (e.g. instruction_override — the same
      field the chat badge shows)
    - run_id / step_id passed through (joins badge events to runs)
    - vuln_id joined via the caller's session rows
    - message_sent rows: tool fields map to empty strings, never
      undefined (the frontend renders what it gets)

    Unattributed (system-level) events pass through with vuln_id None.
    """
    data = event.get("event_data") or {}
    agent_id = event.get("agent_id")
    reason = data.get("reason") or data.get("label") or ""
    label = data.get("label") or ""
    # tool_denied events carry the denial reason at event_data.reason;
    # injection events carry the detection class at event_data.label
    # (audit_helpers convention: log_injection_detected passes label
    # as the `reason` argument, log_tool_denied passes the message).
    if not label and reason and reason in (
        "instruction_override", "role_redefinition", "system_marker",
        "inst_marker", "sys_marker", "system_delimiter",
        "hidden_unicode_zero_width", "hidden_unicode_rtl_override",
        "base64_encoded_instruction",
    ):
        label = reason
    return {
        "id": event.get("id"),
        "timestamp": event.get("created_at"),
        "event_type": event.get("event_type"),
        "tool_name": data.get("tool_name") or "",
        "reason": reason,
        "label": label,
        "run_id": event.get("run_id"),
        "step_id": event.get("step_id"),
        "agent_id": agent_id,
        "vuln_id": vuln_by_agent.get(agent_id) if agent_id else None,
    }


@router.get("/events")
async def get_security_events(
    request: Request,
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Proxy to LettaLocal security events, scoped and mapped.

    Fetches the requested limit from LettaLocal, then filters to the
    caller's agents — the scoped result may be shorter than the limit.
    Acceptable at teaching scale. Filters (event_type, limit) pass
    through to the proxy unchanged.
    """
    letta_client = request.app.state.letta_client

    # Caller's agent set + vuln join key: session rows for this user.
    # agent_id is None (in-code sentinel before first agent creation,
    # agent.py "Ensure None, not empty string") or "" defensively —
    # drop both. One query serves scoping AND the vuln_id join.
    result = await db.execute(
        select(SessionModel.agent_id, SessionModel.vulnerability_id).where(
            SessionModel.user_id == user.id
        )
    )
    owned = [(aid, vid) for aid, vid in result.all() if aid]
    agent_ids = {aid for aid, _ in owned}
    vuln_by_agent = {aid: vid for aid, vid in owned}

    events = await letta_client.get_security_events(
        event_type=event_type,
        limit=limit,
    )
    scoped = [
        e for e in events if not e.get("agent_id") or e.get("agent_id") in agent_ids
    ]
    return {"events": [_map_event(e, vuln_by_agent) for e in scoped]}
