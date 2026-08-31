from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PolicyConfig(BaseModel):
    """Policy configuration governing agent tool usage and behavior."""

    denied_tools: list[str] = Field(
        default_factory=list,
        description="Tools that are explicitly denied for this agent.",
    )
    rules: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured policy rules applied to agent actions.",
    )
    max_calls_per_tool: dict[str, int] = Field(
        default_factory=dict,
        description="Maximum number of calls allowed per tool, keyed by tool name.",
    )
    defaults: dict[str, Any] | None = Field(
        default=None,
        description="Default policy values applied when no explicit rule matches.",
    )
    loop_detection: dict[str, Any] | None = Field(
        default=None,
        description="Configuration for detecting and breaking agent tool-call loops.",
    )


class ToolConfig(BaseModel):
    """Configuration for a single tool available to an agent."""

    name: str = Field(
        ...,
        description="The tool name as referenced by the agent.",
    )
    description: str = Field(
        ...,
        description="Human-readable description of what the tool does.",
    )
    source: str = Field(
        ...,
        description="Origin of the tool — either 'builtin' or 'custom'.",
    )


class ModelSettings(BaseModel):
    """Letta model settings — controls provider behavior."""

    provider_type: str = Field(
        default="openai",
        description="Provider type: 'ollama' for Ollama-hosted models, 'openai' for OpenAI.",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature. 0.0 for deterministic output.",
    )
    enable_reasoner: bool = Field(
        default=False,
        description="Whether to enable reasoning/thinking mode. True for reasoning models like nemotron-3-nano:4b.",
    )


class TokenBudgetConfig(BaseModel):
    """Per-agent token budget (LLM06 unbounded consumption).

    Flows to LettaLocal via agent METADATA keys (token_budget_run /
    token_budget_step / token_budget_context_ratio) — metadata is a
    DECLARED field on CreateAgent/UpdateAgent schemas, so unlike
    loop_detection this needs no LettaLocal API change. The engine's
    TokenBudget (agents/token_budget.py, wired in the v3 agent path)
    enforces after each LLM call; an exceeded budget stops the run
    with max_tokens_exceeded -> RunStatus.failed.
    """

    run: int | None = Field(
        default=None,
        description="Max cumulative tokens per run (token_budget_run).",
    )
    step: int | None = Field(
        default=None,
        description="Max tokens for a single step (token_budget_step).",
    )
    context_ratio: float | None = Field(
        default=None,
        description="Fraction of the context window allowed (token_budget_context_ratio; engine default 0.7).",
    )


class AgentConfig(BaseModel):
    """Full configuration for a defense agent."""

    system_prompt: str = Field(
        ...,
        description="System prompt that defines the agent's persona and instructions.",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names enabled for the agent.",
    )
    policy: PolicyConfig = Field(
        default_factory=PolicyConfig,
        description="Policy configuration governing agent behavior and tool usage.",
    )
    canary: bool = Field(
        default=False,
        description="Whether this configuration is in canary / experimental mode.",
    )
    canary_value: str | None = Field(
        default=None,
        description="The canary token string; wired into a __canary__ memory block at agent creation (LettaLocal has NO enable_canary field — unknown payload fields are silently dropped, extra='ignore').",
    )
    content_validation: bool = Field(
        default=False,
        description="Whether content validation is enabled for agent outputs.",
    )
    documents: list[str] = Field(
        default_factory=list,
        description="List of document identifiers or paths attached to the agent.",
    )
    model: str = Field(
        default="ollama/nemotron-3-nano:4b",
        description="LLM model handle with provider prefix.",
    )
    embedding: str = Field(
        default="ollama/embeddinggemma:latest",
        description="Embedding model for archival memory search.",
    )
    model_settings: ModelSettings = Field(
        default_factory=ModelSettings,
        description="Provider-specific model settings.",
    )
    archival_documents: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Pre-loaded (filename, content) pairs for archival memory insertion.",
    )
    token_budget: TokenBudgetConfig | None = Field(
        default=None,
        description="Per-agent token budget (LLM06); None = unbounded.",
    )
