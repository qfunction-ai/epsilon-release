"""Agent interaction endpoints.

Creates or updates agents via AgentManager, then proxies messages to
LettaLocal. Streaming uses Server-Sent Events (SSE) following Delta's
pure-ASGI pattern: commit DB state before opening the stream, manage
the HTTPX lifecycle properly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.errors import safe_error
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.agent_manager import AgentManager
from app.services.letta_client import LettaClient

logger = logging.getLogger(__name__)
router = APIRouter()

# Shielded abort tasks fired from SSE generator teardown (wiring C).
# create_task is synchronous and the task survives generator teardown,
# but the event loop only keeps WEAK references to tasks — hold them
# here and discard on completion so nothing is GC'd mid-flight.
_abort_tasks: set[asyncio.Task] = set()

# VULN-003 fix (security review 2026-08-29): per-user single-flight
# guard. user.id is in the set while one of the user's runs/streams is
# active; a second concurrent request gets 429 (reject, never queue —
# queueing would hide the single-slot wedge and stack latency).
# Check-and-add is atomic by construction on a single event loop: no
# awaits between the membership check and the add. This is why an
# in-flight SET is used instead of an asyncio.Lock — a check-then-
# acquire Lock pattern is only race-free by implementation detail (the
# uncontended fast path never suspends), and one inserted await would
# reopen the race. Do NOT insert awaits between check and add, ever.
_in_flight: set[int] = set()


class RunRequest(BaseModel):
    """Request body for running an agent."""
    year: int = Field(..., description="OWASP edition year")
    vuln_id: str = Field(..., description="Vulnerability ID, e.g. 'llm01_prompt_injection'")
    code_state: str = Field(..., description="'vulnerable' or 'fixed'")
    # VULN-007 (security review): unbounded messages were forwarded
    # verbatim to the model — memory/queue abuse and accidental
    # context blowouts on a 4B model. 20k chars is far beyond any
    # legitimate exercise prompt. Covers /run and /stream (shared).
    message: str = Field(..., max_length=20_000, description="User message to send to the agent")


class RunResponse(BaseModel):
    """Response from running an agent."""
    session_id: str
    agent_id: str
    response: dict[str, Any]


class ResetRequest(BaseModel):
    """Request body for resetting a chat session."""
    year: int = Field(..., description="OWASP edition year")
    vuln_id: str = Field(..., description="Vulnerability ID, e.g. 'llm01_prompt_injection'")


class ResetResponse(BaseModel):
    """Response from resetting a chat session."""
    reset: bool


@router.delete("/session", response_model=ResetResponse)
async def reset_session(
    body: ResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reset the CALLING user's session for one vulnerability.

    Deletes the Letta agent (cascades steps/messages), then the
    session row. The next /run or /stream mints a fresh session and
    agent with clean context. Scope guard: the user comes from the
    auth token, never from the request body — a student can only
    reset their own chat. Idempotent: no session means nothing to
    do (reset: false).

    NOTE (frontend contract): the reset button is disabled while a
    stream is active — deleting an agent under an in-flight run
    aborts the SSE messily.
    """
    letta_client = _get_letta_client(request)
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.vulnerability_id == f"{body.year}_{body.vuln_id}",
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return ResetResponse(reset=False)

    if session.agent_id:
        # Wiring B (abort plan): abort active runs BEFORE deleting the
        # agent, so reset is honest even with in-flight work. The UI's
        # disable-while-streaming gate is advisory; this is the guarantee.
        aborted = await letta_client.abort_active_runs(session.agent_id)
        if aborted:
            logger.info(f"Reset: aborted {aborted} active run(s) before agent delete")
        try:
            await letta_client.delete_agent(session.agent_id)
        except Exception as exc:
            logger.warning(f"Agent delete during session reset failed (continuing): {exc}")

    await db.delete(session)
    await db.commit()
    logger.info(f"Reset session for user={user.id} vuln={body.vuln_id}")
    return ResetResponse(reset=True)


def _get_letta_client(request: Request) -> LettaClient:
    return request.app.state.letta_client


async def _get_or_create_session(
    db: AsyncSession,
    user: User,
    year: int,
    vuln_id: str,
    code_state: str,
) -> SessionModel:
    """Get an existing session or create a new one.

    For now, one session per user + vulnerability. If the code_state
    changes, the session is updated (not recreated) — the agent_manager
    handles the agent update.

    VULN-004: (user_id, vulnerability_id) has a DB unique constraint.
    If two requests race past the in-flight guard (some future code
    path), the loser's flush raises IntegrityError once the winner's
    row commits — recover by rolling back and re-selecting the
    winner's row. Safe here: this runs before any other writes in
    the request, so the rollback discards nothing else.
    """
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.vulnerability_id == f"{year}_{vuln_id}",
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        session = SessionModel(
            user_id=user.id,
            vulnerability_id=f"{year}_{vuln_id}",
            code_state=code_state,
            agent_id="",  # Will be set by agent_manager
        )
        try:
            db.add(session)
            await db.flush()
        except IntegrityError:
            await db.rollback()
            result = await db.execute(
                select(SessionModel).where(
                    SessionModel.user_id == user.id,
                    SessionModel.vulnerability_id == f"{year}_{vuln_id}",
                )
            )
            session = result.scalar_one()

    return session


@router.post("/run", response_model=RunResponse)
async def run_agent(
    body: RunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run an agent with a message. Creates/updates agent as needed."""
    # VULN-003: single-flight guard — FIRST, before any DB work. Two
    # parallel first-messages for the same vuln would both pass the
    # session-exists check and insert duplicate session rows (the
    # VULN-004 race); rejecting here makes that race unreachable from
    # /run. Check-and-add is atomic: no awaits between.
    if user.id in _in_flight:
        raise HTTPException(
            status_code=429,
            detail="Another agent run is already in progress for this user",
        )
    _in_flight.add(user.id)

    # Everything below owns the slot — the finally guarantees release
    # on EVERY exit path (404, agent-setup failure, run failure,
    # success), so a user can never be permanently wedged.
    try:
        letta_client = _get_letta_client(request)
        manager = AgentManager(letta_client, request.app.state.vuln_loader, get_settings())

        # Get the vulnerability config for the requested code_state
        try:
            vuln_config = await manager.get_config_for_vuln(body.year, body.vuln_id, body.code_state)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        # Get or create session
        session = await _get_or_create_session(db, user, body.year, body.vuln_id, body.code_state)

        # Ensure agent exists and is configured for the right code_state
        if not session.agent_id:
            session.agent_id = None  # Ensure None, not empty string

        vuln_dir = request.app.state.vuln_loader.get_vuln_dir(body.year, body.vuln_id)
        agent_id = await manager.ensure_agent(session, vuln_config, body.code_state, vuln_dir)
        await db.commit()

        # Run the agent
        try:
            response = await letta_client.run_agent(agent_id, body.message)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            # Wiring A (abort plan): the server-side run is typically STILL
            # ACTIVE at this point (timeout signature = wedge cascade).
            # Abort before responding, freeing the inference slot instead
            # of orphaning the run to grind into the next request. Cost:
            # the 502 waits up to ~10s + N abort POSTs — accepted for slot
            # reclamation (Delta review).
            aborted = await letta_client.abort_active_runs(agent_id)
            if aborted:
                logger.info(f"Run failure containment: aborted {aborted} active run(s) for {agent_id}")
            raise HTTPException(status_code=502, detail=safe_error(e)) from e

        return RunResponse(
            session_id=session.id,
            agent_id=agent_id,
            response=response,
        )
    finally:
        _in_flight.discard(user.id)


@router.post("/stream")
async def stream_agent(
    body: RunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream an agent response via SSE.

    Commits DB state before opening the stream. The stream is a pure ASGI
    response — no DB access during streaming.
    """
    # VULN-003: single-flight guard — FIRST, before any DB work (same
    # placement rationale as /run: a parallel first-message would
    # create duplicate session rows before hitting the guard). REJECT
    # before acquiring, never await a held slot (queueing is the
    # anti-pattern). Atomic: no awaits between check and add. The
    # generator's finally is the release point; the handler-level
    # except releases if response construction fails before the
    # generator takes ownership.
    if user.id in _in_flight:
        raise HTTPException(
            status_code=429,
            detail="Another agent run is already in progress for this user",
        )
    _in_flight.add(user.id)

    # Everything below owns the slot until the response is
    # successfully returned — then the generator's finally is the
    # release point. Any failure before that (404, DB error, agent
    # setup) hits the except here, so the slot can never leak.
    try:
        letta_client = _get_letta_client(request)
        manager = AgentManager(letta_client, request.app.state.vuln_loader, get_settings())

        try:
            vuln_config = await manager.get_config_for_vuln(body.year, body.vuln_id, body.code_state)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        session = await _get_or_create_session(db, user, body.year, body.vuln_id, body.code_state)

        if not session.agent_id:
            session.agent_id = None

        vuln_dir = request.app.state.vuln_loader.get_vuln_dir(body.year, body.vuln_id)
        agent_id = await manager.ensure_agent(session, vuln_config, body.code_state, vuln_dir)
        await db.commit()

        async def event_stream():
            """Generate SSE events from LettaLocal stream.

            Letta's /messages endpoint with streaming=true already returns
            SSE-formatted lines (data: {...}\\n\\n). Yield them directly without
            re-wrapping to avoid double encoding (data: data: {...}).

            Wiring C (abort plan): capture run_id from any event that carries
            it (pings arrive early and repeatedly). If the stream does NOT
            complete normally — client disconnect (GeneratorExit/Cancelled)
            OR mid-stream error — fire a shielded abort so the server-side
            run stops instead of grinding the single-slot inference queue.
            A completed-normally flag keeps healthy turns silent (Delta
            review: per-turn abort noise would be misread as a bug later).

            VULN-003: the finally below releases the single-flight slot
            FIRST, then fires the abort — the abort is a shielded
            background task, so releasing first lets the user retry
            immediately while the abort reclaims the inference slot.
            """
            run_id: str | None = None
            stream_completed = False
            try:
                async for line in letta_client.stream_agent(agent_id, body.message):
                    payload = line[6:] if line.startswith("data: ") else line
                    # Capture run_id from the first event that carries it
                    if run_id is None and payload.lstrip().startswith("{"):
                        try:
                            evt = json.loads(payload)
                            rid = evt.get("run_id")
                            if isinstance(rid, str) and rid:
                                run_id = rid
                        except (json.JSONDecodeError, ValueError):
                            pass
                    # Letta returns SSE-formatted lines starting with "data: "
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
                    else:
                        yield f"data: {line}\n\n"
                # Letta's stream ended normally — the run is terminal
                # server-side. Mark BEFORE the [DONE] yield so a client
                # disconnect exactly at [DONE] does not fire a spurious
                # abort of an already-finished run.
                stream_completed = True
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'error': safe_error(e)})}\n\n"
            finally:
                # VULN-003: release the slot before the abort wiring —
                # see docstring.
                _in_flight.discard(user.id)
                if not stream_completed:
                    if run_id or session.agent_id:
                        async def _fire_abort() -> None:
                            try:
                                if run_id:
                                    await letta_client.abort_run(run_id)
                                    logger.info(f"Stream teardown abort fired for run {run_id}")
                                else:
                                    n = await letta_client.abort_active_runs(session.agent_id)
                                    if n:
                                        logger.info(
                                            f"Stream teardown abort fired for agent {session.agent_id} ({n} run(s))"
                                        )
                            except Exception as abort_exc:
                                logger.warning(f"teardown abort task failed (continuing): {abort_exc}")

                        task = asyncio.create_task(_fire_abort())
                        _abort_tasks.add(task)
                        task.add_done_callback(_abort_tasks.discard)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception:
        # Response construction failed before the generator could take
        # ownership of the slot — release it here (double-discard is a
        # no-op on a set).
        _in_flight.discard(user.id)
        raise


@router.get("/messages/{session_id}")
async def get_messages(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get message history for a session (proxy to LettaLocal)."""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    letta_client = _get_letta_client(request)
    try:
        return await letta_client.get_messages(session.agent_id)
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        raise HTTPException(status_code=502, detail=safe_error(e)) from e
