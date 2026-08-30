"""LettaClient — async singleton wrapping the LettaLocal REST API.

All HTTP calls go through httpx.AsyncClient. LettaLocal runs at the URL
specified in config (default http://localhost:8283). The client is a
singleton: one instance per process, shared across requests.

Usage:
    client = LettaClient("http://localhost:8283")
    agent_id = await client.create_agent(config)
    response = await client.run_agent(agent_id, "Hello")
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.schemas.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class LettaClient:
    """Singleton async client for the LettaLocal REST API.

    Wraps httpx.AsyncClient for all HTTP calls. Methods map 1:1 to
    LettaLocal REST endpoints under /v1/.
    """

    _instance: LettaClient | None = None

    def __new__(cls, *args: Any, **kwargs: Any) -> LettaClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, base_url: str = "http://localhost:8283") -> None:
        # Guard against re-initialisation of the singleton
        if getattr(self, "_initialised", False):
            return

        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            # read=600: covers every HEALTHY turn class observed; the
            # 15-min known-hang turns are the test suite's own FAIL
            # class (LLM09_503_INVESTIGATION.md). Note: suite runs are
            # still bounded by the SUITE's httpx client (read=300).
            timeout=httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=5.0),
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "letta-client/1.0",  # fork checks UA for SDK version
            },
        )
        self._initialised = True
        logger.info(f"LettaClient initialised — base_url={self.base_url}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_error(exc: httpx.HTTPError, operation: str) -> None:
        """Translate httpx errors into FastAPI HTTPException."""
        if isinstance(exc, httpx.HTTPStatusError):
            # Attempt to extract detail from the LettaLocal error body
            detail = exc.response.text
            try:
                body = exc.response.json()
                detail = body.get("detail", body.get("message", detail))
            except (json.JSONDecodeError, ValueError):
                body = None  # non-JSON error body; keep the raw-text detail set above
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"LettaLocal {operation} failed: {detail}",
            ) from exc

        # Connection / timeout / network errors
        # Exception class in the detail: the 2026-08-27 chip-audit 503s
        # had EMPTY {exc} text, making the class unidentifiable
        # retroactively (LLM09_503_INVESTIGATION.md). Type name first.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LettaLocal {operation} unavailable: {type(exc).__name__}: {exc}",
        ) from exc

    def _build_agent_payload(self, config: AgentConfig) -> dict[str, Any]:
        """Convert an AgentConfig into the LettaLocal create/modify payload.

        The system prompt goes in the persona memory block — do NOT also
        set "system_prompt" in the payload, that would duplicate content
        in the context window.
        """
        payload: dict[str, Any] = {
            "model": config.model,
            "embedding": config.embedding,
            "model_settings": config.model_settings.model_dump(),
            "tools": list(config.tools),
            "include_base_tools": False,
            # nemotron-3-nano:4b is a reasoning model. Letta's
            # enable_reasoner=True sends chat_template_args with
            # enable_thinking=True to Ollama, which enables reasoning traces.
            "enable_reasoner": True,
        }

        # Memory blocks — persona block IS the system prompt in Letta.
        # Docs: "For most chat applications, we recommend creating a
        # human block and a persona block."
        payload["memory_blocks"] = [
            {
                "label": "persona",
                "value": config.system_prompt,
                # Letta auto-generates description for persona blocks
            },
            {
                "label": "human",
                "value": "Student studying OWASP LLM vulnerabilities.",
                # Letta auto-generates description for human blocks
            },
        ]

        # Canary — LettaLocal has NO enable_canary field (silently
        # dropped by Pydantic extra="ignore"; sending it made every
        # config-authored canary decorative while the lazy path minted
        # random ones). The wiring runs through a __canary__ memory
        # block: load_canary finds it at agent init and points both
        # CanaryChecker (tool args) and CanaryOutputFilter (assistant
        # text, streaming + non-streaming) at THIS value.
        if config.canary:
            if config.canary_value:
                payload["memory_blocks"].append(
                    {
                        "label": "__canary__",
                        "value": config.canary_value,
                    }
                )
            else:
                # canary: true without canary_value — LettaLocal's lazy
                # path will mint a random canary (decorative relative to
                # any prompt-embedded string). Every Epsilon config
                # declares canary_value; this warns if one drifts away.
                logger.warning(
                    "canary=true but canary_value not set — random canary will be generated"
                )

        # Content validation flag — sent via metadata dict.
        # Top-level field is silently dropped by Pydantic extra="ignore".
        # metadata IS persisted and read by init_security() in LettaLocal.
        if config.content_validation:
            if "metadata" not in payload:
                payload["metadata"] = {}
            payload["metadata"]["enable_content_validation"] = True

        return payload

    # ------------------------------------------------------------------
    # Tool calling mode pin
    # ------------------------------------------------------------------

    async def _pin_tool_calling_mode(self, agent_id: str) -> None:
        """Pin tool_calling_mode=prompt on a freshly created agent.

        MODEL-SPECIFIC: nemotron-3-nano:4b cannot use Ollama's native
        tool-calling API — in native mode it prints tool-call JSON as
        assistant text (5/5 garbage, experiment arm D, 2026-08-26).
        With mode=None the per-agent probe coin-flips between prompt
        and native. Prompt mode injects the framework's tool-calling
        instructions, which this model follows. If Epsilon ever swaps
        to a model that handles native tool-calling, revisit this pin.

        The LettaLocal API requires the FULL llm_config for PATCH (a
        partial one 422s on required fields), so we GET the
        probe-resolved config, flip only the mode, and PATCH it back.
        Warning-not-fail by design: the test suite's coherence guards
        (commit 1a74a71) are the backstop if the pin ever stops
        applying (UpdateAgent.llm_config is a deprecated surface).
        """
        try:
            resp = await self._client.get(f"/v1/agents/{agent_id}")
            resp.raise_for_status()
            llm_config = resp.json().get("llm_config")
            if not isinstance(llm_config, dict):
                logger.warning(f"No llm_config on {agent_id}; tool_calling_mode not pinned")
                return
            if llm_config.get("tool_calling_mode") == "prompt":
                return  # already pinned (idempotent)
            llm_config["tool_calling_mode"] = "prompt"
            resp = await self._client.patch(f"/v1/agents/{agent_id}", json={"llm_config": llm_config})
            resp.raise_for_status()
            # Verify the PATCH took
            check = await self._client.get(f"/v1/agents/{agent_id}")
            mode = check.json().get("llm_config", {}).get("tool_calling_mode")
            if mode == "prompt":
                logger.info(f"Pinned tool_calling_mode=prompt for {agent_id}")
            else:
                logger.warning(f"tool_calling_mode pin did not stick for {agent_id} (resolved {mode})")
        except httpx.HTTPError as exc:
            logger.warning(f"tool_calling_mode pin failed for {agent_id}: {exc}")

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    async def ensure_tools_registered(self) -> None:
        """Register custom Epsilon tools with Letta if they don't exist.

        Called on startup. Letta's DB can be reset independently of Epsilon,
        so custom tools registered via the API may disappear. This method
        reads the tool source from app/tools/ and registers it.

        If the tool already exists (by name), it's left alone — we don't
        overwrite a potentially newer version.
        """
        import pathlib

        tools_dir = pathlib.Path(__file__).parent.parent / "tools"

        # Map of tool name -> (source file, description, tags)
        custom_tools = [
            (
                "execute_code",
                tools_dir / "execute_code.py",
                "Execute Python code locally. Vulnerable version: no input validation, no import restrictions.",
                ["epsilon", "code-execution", "vulnerable"],
            ),
        ]

        for name, source_path, description, tags in custom_tools:
            # Check if tool already exists
            try:
                resp = await self._client.get("/v1/tools/")
                resp.raise_for_status()
                existing = resp.json()
                if any(t.get("name") == name for t in existing):
                    logger.debug(f"Tool '{name}' already registered — skipping")
                    continue
            except httpx.HTTPError as exc:
                logger.warning(f"Failed to check existing tools: {exc}")
                continue

            # Register the tool
            source_code = source_path.read_text()
            payload = {
                "description": description,
                "source_type": "python",
                "source_code": source_code,
                "tags": tags,
                "return_char_limit": 50000,
            }
            try:
                resp = await self._client.post("/v1/tools/", json=payload)
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"Registered tool '{name}' (id={data.get('id')})")
            except httpx.HTTPError as exc:
                logger.error(f"Failed to register tool '{name}': {exc}")

    # ------------------------------------------------------------------
    # Post-creation configuration (policy, tools, archival memory)
    # ------------------------------------------------------------------

    async def _set_tool_call_policy(self, agent_id: str, config: AgentConfig) -> None:
        """Set the tool call policy via the dedicated policy API endpoint.

        LettaLocal stores policy in a separate table (tool_call_policies),
        not in the agent record. The policy must be set via
        PUT /v1/agents/{id}/policy — it's silently ignored in the agent
        creation/update body. loop_detection joined the API in
        LettaLocal 0.16.28 (schema extra=forbid).
        """
        policy = config.policy
        payload: dict[str, Any] = {
            "denied_tools": policy.denied_tools,
            "rules": policy.rules,
            "max_calls_per_tool": policy.max_calls_per_tool,
        }
        if policy.defaults:
            payload["defaults"] = policy.defaults
        # loop_detection: exposed on the policy API in LettaLocal
        # 0.16.28 (extra=forbid — wrong keys 422 loudly). Only
        # llm06's fixed state configures it.
        if policy.loop_detection:
            payload["loop_detection"] = policy.loop_detection

        try:
            resp = await self._client.put(
                f"/v1/agents/{agent_id}/policy",
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Raise loudly: a swallowed policy failure leaves the agent
            # silently defenseless (observed 2026-08-20 — one invalid
            # regex rule 400'd the entire PUT and the "fixed" agent ran
            # with no policy at all). In a security teaching app, a
            # half-configured agent is worse than a failed request.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LettaLocal rejected the tool call policy "
                       f"(agent {agent_id}): {exc}",
            ) from exc

    async def _sync_tools(self, agent_id: str, desired_tools: list[str]) -> None:
        """Ensure the agent has exactly the desired tool set.

        LettaLocal's UpdateAgent uses tool_ids, not tool_names. The
        attach/detach endpoints are the correct way to modify an agent's
        tools after creation.
        """
        try:
            resp = await self._client.get(f"/v1/agents/{agent_id}/tools")
            resp.raise_for_status()
            current = {t["name"]: t["id"] for t in resp.json()}
        except httpx.HTTPError as exc:
            logger.error(f"Failed to list tools for {agent_id}: {exc}")
            return

        try:
            resp = await self._client.get("/v1/tools/")
            resp.raise_for_status()
            all_tools = {t["name"]: t["id"] for t in resp.json()}
        except httpx.HTTPError as exc:
            logger.error(f"Failed to list all tools: {exc}")
            return

        # Detach tools that should be removed
        for name, tool_id in current.items():
            if name not in desired_tools:
                try:
                    await self._client.patch(
                        f"/v1/agents/{agent_id}/tools/detach/{tool_id}"
                    )
                except httpx.HTTPError as exc:
                    logger.warning(f"Failed to detach tool {name}: {exc}")

        # Attach tools that should be added
        for name in desired_tools:
            if name not in current and name in all_tools:
                try:
                    await self._client.patch(
                        f"/v1/agents/{agent_id}/tools/attach/{all_tools[name]}"
                    )
                except httpx.HTTPError as exc:
                    logger.warning(f"Failed to attach tool {name}: {exc}")

    async def _load_archival_documents(
        self, agent_id: str, documents: list[tuple[str, str]]
    ) -> None:
        """Load pre-resolved documents into the agent's archival memory.

        Clears existing archival memory first, then inserts each document
        as a separate passage with source tags. Skips the delete+insert
        cycle if the document set hasn't changed (detected by comparing
        the set of passage tags).
        """
        try:
            resp = await self._client.get(f"/v1/agents/{agent_id}/archival-memory")
            resp.raise_for_status()
            existing = resp.json()
        except httpx.HTTPError as exc:
            logger.error(f"Failed to list archival memory for {agent_id}: {exc}")
            return

        desired_tags = {name for name, _ in documents}
        existing_tags = set()
        for passage in existing:
            for tag in passage.get("tags") or []:
                existing_tags.add(tag)

        if existing_tags == desired_tags and len(existing) == len(documents):
            logger.debug("Archival memory already has correct documents — skipping reload")
            return

        # Clear existing archival memory
        for passage in existing:
            pid = passage.get("id")
            if pid:
                try:
                    await self._client.delete(
                        f"/v1/agents/{agent_id}/archival-memory/{pid}"
                    )
                except httpx.HTTPError as exc:
                    logger.warning(f"Failed to delete passage {pid}: {exc}")

        # Insert new documents (retry once on transient failure —
        # container churn during stack operations can kill inserts)
        inserted = 0
        for name, content in documents:
            ok = False
            for attempt in (1, 2):
                try:
                    resp = await self._client.post(
                        f"/v1/agents/{agent_id}/archival-memory",
                        json={"text": content, "tags": [name]},
                    )
                    resp.raise_for_status()
                    logger.info(f"Loaded document '{name}' into archival memory")
                    ok = True
                    break
                except httpx.HTTPError as exc:
                    logger.error(
                        f"Failed to insert document '{name}' (attempt {attempt}): {exc}"
                    )
            if ok:
                inserted += 1

        # Verify after load: re-list and confirm the passage count matches.
        # A silently-empty archival memory is otherwise invisible until a
        # student's demo fails (observed 2026-08-20 on a user agent).
        if inserted != len(documents):
            logger.error(
                f"ARCHIVAL LOAD INCOMPLETE for {agent_id}: inserted "
                f"{inserted}/{len(documents)} documents"
            )
        try:
            resp = await self._client.get(f"/v1/agents/{agent_id}/archival-memory")
            resp.raise_for_status()
            final = resp.json()
            if len(final) != len(documents):
                logger.error(
                    f"ARCHIVAL VERIFY FAILED for {agent_id}: expected "
                    f"{len(documents)} passages, found {len(final)}"
                )
            else:
                logger.info(
                    f"Archival verify OK for {agent_id}: {len(final)} passages"
                )
        except httpx.HTTPError as exc:
            logger.error(f"Archival verify list failed for {agent_id}: {exc}")

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    async def create_agent(self, config: AgentConfig) -> str:
        """Create a new agent in LettaLocal.

        Returns the agent_id (a string) that can be used for subsequent
        run_agent / update_agent / stream_agent calls.
        """
        payload = self._build_agent_payload(config)
        # Generate a readable name — sanitize to filesystem-safe characters
        import re
        first_line = config.system_prompt.strip().split("\n")[0][:60]
        safe_name = re.sub(r"[^a-zA-Z0-9 -]", "", first_line).strip().replace(" ", "-").lower()
        payload["name"] = f"epsilon-{safe_name}"[:80]

        try:
            resp = await self._client.post("/v1/agents/", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, "create_agent")
            raise  # _handle_error always raises, but satisfy type checker

        data = resp.json()
        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LettaLocal create_agent returned no agent ID",
            )
        logger.info(f"Created agent {agent_id}")

        # Pin prompt-mode tool calling before any message runs — see
        # _pin_tool_calling_mode for the model-specific rationale.
        await self._pin_tool_calling_mode(agent_id)

        # Post-creation configuration: policy, tools, and archival documents
        # cannot be set in the agent creation body — they require separate
        # API calls to dedicated endpoints.
        await self._set_tool_call_policy(agent_id, config)
        if config.archival_documents:
            await self._load_archival_documents(agent_id, config.archival_documents)

        return str(agent_id)

    async def update_agent(self, agent_id: str, config: AgentConfig) -> None:
        """Update an existing agent in place.

        Swaps the persona (system prompt), tool list, and policy while
        preserving the agent ID, memory blocks, and conversation history.
        This is the key operation for toggling between vulnerable and fixed
        code states without losing the student's conversation.

        The persona block is updated via the block update endpoint
        (PATCH /v1/agents/{id}/core-memory/blocks/persona). The fork
        calls rebuild_system_prompt_async() automatically after the block
        update — no separate system prompt update needed.

        Tools are synced via attach/detach endpoints (tool_names in the
        PATCH body is silently ignored by LettaLocal). Policy is set via
        the dedicated PUT /v1/agents/{id}/policy endpoint.
        """
        # 1. Update the persona block (system prompt) via block update endpoint
        block_payload = {"value": config.system_prompt}
        try:
            resp = await self._client.patch(
                f"/v1/agents/{agent_id}/core-memory/blocks/persona",
                json=block_payload,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, f"update_persona_block({agent_id})")
            raise

        # 2. Update metadata (content validation flag) via agent PATCH
        agent_payload: dict[str, Any] = {
            "model_settings": config.model_settings.model_dump(),
        }
        if config.content_validation:
            agent_payload["metadata"] = {"enable_content_validation": True}

        try:
            resp = await self._client.patch(
                f"/v1/agents/{agent_id}",
                json=agent_payload,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, f"update_agent({agent_id})")
            raise

        # 3. Sync tools via attach/detach endpoints
        await self._sync_tools(agent_id, list(config.tools))

        # 4. Update policy via dedicated policy API endpoint
        await self._set_tool_call_policy(agent_id, config)

        # 5. Reload archival documents if the document set changed
        if config.archival_documents:
            await self._load_archival_documents(agent_id, config.archival_documents)

        logger.info(f"Updated agent {agent_id} — swapped config in place")

    async def reset_messages(self, agent_id: str) -> None:
        """Clear all in-context messages for an agent.

        NOTE (0.16.22 drift): this endpoint returns 200 but does NOT
        clear in-context messages on LettaLocal 0.16.22 (verified
        empirically 2026-08-20: message list identical before/after).
        Kept for interface compatibility; agent_manager now recreates
        the agent on code_state toggle instead of relying on this.
        """
        try:
            resp = await self._client.patch(
                f"/v1/agents/{agent_id}/reset-messages",
                json={"add_default_initial_messages": False},
            )
            resp.raise_for_status()
            logger.info(f"Reset messages for agent {agent_id}")
        except httpx.HTTPError as exc:
            logger.error(f"Failed to reset messages for {agent_id}: {exc}")

    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent from LettaLocal.

        Used on code_state toggle: the agent is recreated fresh with the
        new state's config (clean context, correct policy, correct docs).
        """
        try:
            resp = await self._client.delete(f"/v1/agents/{agent_id}")
            resp.raise_for_status()
            logger.info(f"Deleted agent {agent_id}")
        except httpx.HTTPError as exc:
            logger.error(f"Failed to delete agent {agent_id}: {exc}")

    # ------------------------------------------------------------------
    # Run cancellation (LettaLocal >= 0.16.29)
    # ------------------------------------------------------------------

    async def abort_run(self, run_id: str) -> dict[str, Any]:
        """POST /v1/runs/{run_id}/abort.

        Best-effort, never raises: abort wiring must not create new
        failure modes. On pre-0.16.29 LettaLocal the endpoint 404s and
        we degrade gracefully to orphaned-run behavior. Short per-call
        timeout — an abort must never wait the full read budget.
        """
        try:
            resp = await self._client.post(f"/v1/runs/{run_id}/abort", timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f"abort_run({run_id}) best-effort failed (continuing): {exc}")
            return {}

    async def abort_active_runs(self, agent_id: str) -> int:
        """Abort every active run for an agent. Returns count aborted.

        Discovery via GET /v1/runs?agent_id=...&active=true (pre-existing
        LettaLocal surface). Best-effort, never raises.
        """
        count = 0
        try:
            resp = await self._client.get(
                "/v1/runs",
                params={"agent_id": agent_id, "active": "true"},
                timeout=10.0,
            )
            resp.raise_for_status()
            runs = resp.json()
            if isinstance(runs, list):
                for run in runs:
                    rid = run.get("id") if isinstance(run, dict) else None
                    if rid:
                        await self.abort_run(rid)
                        count += 1
        except Exception as exc:
            logger.warning(f"abort_active_runs({agent_id}) best-effort failed (continuing): {exc}")
        return count

    async def get_messages(self, agent_id: str) -> dict[str, Any]:
        """Fetch message history for an agent (proxy endpoint support)."""
        try:
            resp = await self._client.get(f"/v1/agents/{agent_id}/messages")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            self._handle_error(exc, f"get_messages({agent_id})")
            raise

    async def run_agent(self, agent_id: str, message: str) -> dict[str, Any]:
        """Send a user message to an agent and return the full response.

        Uses streaming=false (synchronous mode). The response dict
        contains the agent's messages and usage statistics.
        """
        payload = {
            "messages": [{"role": "user", "content": message}],
        }

        try:
            resp = await self._client.post(
                f"/v1/agents/{agent_id}/messages",
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, f"run_agent({agent_id})")
            raise

        data = resp.json()
        logger.debug(f"run_agent({agent_id}) — response keys: {list(data.keys())}")
        return data

    async def stream_agent(
        self, agent_id: str, message: str
    ) -> AsyncGenerator[str, None]:
        """Stream an agent response via Server-Sent Events (SSE).

        Uses the non-deprecated POST /v1/agents/{id}/messages endpoint with
        streaming=true. Yields raw SSE lines as they arrive from LettaLocal.
        The caller is responsible for parsing the SSE frames and forwarding
        them to the client.
        """
        payload = {
            "messages": [{"role": "user", "content": message}],
            "streaming": True,
            "stream_tokens": True,    # token-level streaming for real-time UX
            "include_pings": True,     # keepalive — prevents timeout on long runs
        }

        try:
            async with self._client.stream(
                "POST",
                f"/v1/agents/{agent_id}/messages",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        yield line
        except httpx.HTTPError as exc:
            self._handle_error(exc, f"stream_agent({agent_id})")
            raise

    # ------------------------------------------------------------------
    # Security & observability proxies
    # ------------------------------------------------------------------

    async def get_security_events(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Proxy to LettaLocal GET /v1/security/events.

        Returns a list of security event dicts. Supports optional
        filtering by agent_id and event_type.
        """
        params: dict[str, Any] = {"limit": limit}
        if agent_id is not None:
            params["agent_id"] = agent_id
        if event_type is not None:
            params["event_type"] = event_type

        try:
            resp = await self._client.get("/v1/security/events", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, "get_security_events")
            raise

        data = resp.json()
        # LettaLocal may return a list directly or wrap in {"events": [...]}
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "events" in data:
            return data["events"]
        return []

    async def get_observability(
        self, agent_id: str | None = None
    ) -> dict[str, Any]:
        """Proxy to LettaLocal GET /v1/observability/overview.

        Returns an observability overview dict with run counts, token
        totals, tool call distribution, and security event counts.
        """
        params: dict[str, Any] = {}
        if agent_id is not None:
            params["agent_id"] = agent_id

        try:
            resp = await self._client.get(
                "/v1/observability/overview", params=params
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_error(exc, "get_observability")
            raise

        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client. Call on application shutdown."""
        await self._client.aclose()
        logger.info("LettaClient httpx client closed")

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset the singleton instance (for testing)."""
        if cls._instance is not None:
            cls._instance = None
