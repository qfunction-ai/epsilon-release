"""AgentManager — orchestrates agent lifecycle for Epsilon vulnerability sessions.

The key insight: toggling between vulnerable and fixed code states does NOT
delete + recreate the agent. It calls LettaClient.update_agent() which swaps
the system prompt, tool list, and policy while preserving the agent ID, memory
blocks, and conversation history. Students keep their conversation when
toggling between vulnerable and fixed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.config import Settings
from app.schemas.agent_config import AgentConfig, ModelSettings, PolicyConfig
from app.schemas.vulnerability import VulnerabilityConfig
from app.services.letta_client import LettaClient
from app.services.vuln_loader import VulnLoader

logger = logging.getLogger(__name__)


@runtime_checkable
class Session(Protocol):
    """Minimal session interface required by AgentManager.

    The real SQLAlchemy Session model (app.models.session.Session) will
    satisfy this protocol. Tests can use a simple dataclass or Mock.
    """

    agent_id: str | None
    code_state: str | None


class AgentManager:
    """Manages agent creation, update, and config resolution for Epsilon.

    Works with LettaClient to create/update agents in LettaLocal and with
    VulnLoader to resolve vulnerability-specific agent configurations.
    """

    def __init__(self, letta_client: LettaClient, vuln_loader: VulnLoader, settings: Settings) -> None:
        self.letta_client = letta_client
        self.vuln_loader = vuln_loader
        self.settings = settings

    async def ensure_agent(
        self,
        session: Session,
        vuln_config: VulnerabilityConfig,
        code_state: str,
        vuln_dir: Path | None = None,
    ) -> str:
        """Ensure the session has an agent configured for the current code_state.

        Three cases:
        1. Session has no agent_id → create a new agent with the config.
           Store agent_id and code_state on the session.
        2. Session has agent_id but code_state changed → update the agent
           in place (swap system prompt, tools, policy). Keep agent_id.
           This preserves memory blocks and conversation history.
        3. Session has agent_id and code_state hasn't changed → no-op.
           Return the existing agent_id.

        Returns the agent_id (str).
        """
        agent_config = self._vuln_config_to_agent_config(vuln_config, self.settings, vuln_dir)

        # Case 1: no agent yet — create one
        if session.agent_id is None:
            agent_id = await self.letta_client.create_agent(agent_config)
            session.agent_id = agent_id
            session.code_state = code_state
            logger.info(
                f"Created agent {agent_id} for code_state='{code_state}'"
            )
            return agent_id

        # Case 2: agent exists but code_state changed — recreate the agent.
        #
        # Update-in-place was the original design (swap config, reset
        # messages), but two LettaLocal 0.16.22 behaviors break it:
        #   1. reset-messages returns 200 but does NOT clear in-context
        #      messages (verified empirically) — the previous state's
        #      conversation contaminated the new state
        #   2. a single invalid policy rule 400s the whole policy PUT,
        #      which the client logs and swallows — the "fixed" agent
        #      silently ran with NO policy
        # Recreating guarantees: fresh context, correct persona, correct
        # policy, correct docs. Agents are scratch state (sessions are
        # keyed per user/vuln), so identity churn is acceptable.
        if session.code_state != code_state:
            old_agent_id = session.agent_id
            await self.letta_client.delete_agent(session.agent_id)
            new_agent_id = await self.letta_client.create_agent(agent_config)
            session.agent_id = new_agent_id
            session.code_state = code_state
            logger.info(
                f"Toggled code_state → '{code_state}': "
                f"recreated agent {old_agent_id} → {new_agent_id}"
            )
            return new_agent_id

        # Case 3: agent exists and code_state unchanged — no-op
        logger.debug(
            f"Agent {session.agent_id} already configured for "
            f"code_state='{code_state}' — no-op"
        )
        return session.agent_id

    async def get_config_for_vuln(
        self,
        year: int,
        vuln_id: str,
        code_state: str,
    ) -> VulnerabilityConfig:
        """Resolve the VulnerabilityConfig for a given vulnerability and state.

        Uses VulnLoader to fetch the vulnerable.yaml or fixed.yaml for the
        vulnerability. ``code_state`` should be either "vulnerable" or "fixed".

        Raises ValueError if the config is not found.
        """
        if code_state == "vulnerable":
            config = self.vuln_loader.get_vulnerable_config(year, vuln_id)
        elif code_state == "fixed":
            config = self.vuln_loader.get_fixed_config(year, vuln_id)
        else:
            raise ValueError(
                f"Invalid code_state '{code_state}' — "
                f"expected 'vulnerable' or 'fixed'"
            )

        if config is None:
            raise ValueError(
                f"No {code_state} config found for "
                f"vulnerability {year}/{vuln_id}"
            )

        return config

    @staticmethod
    def _vuln_config_to_agent_config(
        vuln_config: VulnerabilityConfig,
        settings: Settings,
        vuln_dir: Path | None = None,
    ) -> AgentConfig:
        """Convert a VulnerabilityConfig (dict-based policy) to an AgentConfig
        (PolicyConfig-based policy) with infrastructure settings injected.

        VulnerabilityConfig.policy is a dict[str, Any] loaded from YAML.
        AgentConfig.policy is a PolicyConfig pydantic model. This conversion
        bridges the two schemas.

        Model, embedding, and model_settings come from backend config, not the YAML.

        If vuln_dir is provided, document filenames in vuln_config.documents
        are resolved to (stem, content) pairs for archival memory insertion.
        """
        # Derive provider_type from model prefix
        provider_type = "ollama" if settings.OLLAMA_MODEL.lower().startswith("ollama/") else "openai"

        model_settings = ModelSettings(
            provider_type=provider_type,
            temperature=0.0,
        )

        policy = PolicyConfig(
            denied_tools=vuln_config.policy.get("denied_tools", []),
            rules=vuln_config.policy.get("rules", []),
            max_calls_per_tool=vuln_config.policy.get("max_calls_per_tool", {}),
            defaults=vuln_config.policy.get("defaults"),
            loop_detection=vuln_config.policy.get("loop_detection"),
        )

        # Resolve document filenames to (stem, content) pairs
        archival_docs: list[tuple[str, str]] = []
        if vuln_dir and vuln_config.documents:
            for doc_path in vuln_config.documents:
                full_path = vuln_dir / doc_path
                if not full_path.exists():
                    # Try documents/ subdirectory
                    full_path = vuln_dir / "documents" / doc_path
                if full_path.exists():
                    archival_docs.append((full_path.stem, full_path.read_text()))
                else:
                    logger.warning(f"Document not found: {full_path}")

        return AgentConfig(
            system_prompt=vuln_config.system_prompt,
            tools=vuln_config.tools,
            policy=policy,
            canary=vuln_config.canary,
            canary_value=vuln_config.canary_value,
            content_validation=vuln_config.content_validation,
            documents=vuln_config.documents,
            model=settings.OLLAMA_MODEL,
            embedding=settings.LETTA_EMBEDDING_MODEL,
            model_settings=model_settings,
            archival_documents=archival_docs,
            # LLM06 token budget: raw dict from the YAML flows into the
            # typed config here (pydantic coerces {run, step, context_ratio}).
            token_budget=vuln_config.token_budget,
        )
