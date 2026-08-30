"""Unit tests for AgentManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.vulnerability import VulnerabilityConfig
from app.services.agent_manager import AgentManager


@pytest.fixture
def mock_letta_client():
    """Mock LettaClient with async methods."""
    client = MagicMock()
    client.create_agent = AsyncMock(return_value="agent-123")
    client.update_agent = AsyncMock(return_value=None)
    client.delete_agent = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_vuln_loader():
    """Mock VulnLoader — empty by default, patch per-test as needed."""
    loader = MagicMock()
    loader.get_vulnerable_config = MagicMock(return_value=None)
    loader.get_fixed_config = MagicMock(return_value=None)
    return loader


@pytest.fixture
def mock_settings():
    """Mock Settings with Ollama model and embedding config."""
    settings = MagicMock()
    settings.OLLAMA_MODEL = "ollama/nemotron-3-nano:4b"
    settings.LETTA_EMBEDDING_MODEL = "ollama/embeddinggemma:latest"
    return settings


@pytest.fixture
def vuln_config():
    """A test VulnerabilityConfig."""
    return VulnerabilityConfig(
        system_prompt="You are a test assistant.",
        tools=["web_search"],
        policy={
            "denied_tools": [],
            "rules": [],
            "defaults": {"action": "allow"},
        },
        canary=False,
        content_validation=False,
        documents=[],
    )


@pytest.fixture
def fixed_config():
    """A test fixed VulnerabilityConfig."""
    return VulnerabilityConfig(
        system_prompt="You are a hardened assistant. CANARY-abc123",
        tools=["web_search"],
        policy={
            "denied_tools": [],
            "rules": [{"name": "block-evil", "condition": {}, "action": "deny", "priority": 100}],
            "defaults": {"action": "deny"},
        },
        canary=True,
        content_validation=True,
        documents=[],
    )


@pytest.fixture
def mock_session():
    """A mock session object matching the Session Protocol."""
    session = MagicMock()
    session.agent_id = None
    session.code_state = None
    return session


@pytest.mark.asyncio
async def test_ensure_agent_creates_when_no_agent_id(mock_letta_client, mock_vuln_loader, mock_settings, vuln_config, mock_session):
    """Test: ensure_agent creates agent when session has no agent_id."""
    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    agent_id = await manager.ensure_agent(mock_session, vuln_config, "vulnerable")

    assert agent_id == "agent-123"
    assert mock_session.agent_id == "agent-123"
    assert mock_session.code_state == "vulnerable"
    mock_letta_client.create_agent.assert_called_once()
    mock_letta_client.update_agent.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_agent_recreates_when_code_state_changes(mock_letta_client, mock_vuln_loader, mock_settings, vuln_config, mock_session):
    """Test: code_state change RECREATES the agent (delete + create), not update-in-place.

    Toggle-recreate semantics (agent_manager Case 2): update-in-place was
    replaced after LettaLocal 0.16.22 findings (reset-messages does not
    clear in-context messages; one invalid rule 400s the whole policy PUT).
    Recreating guarantees fresh context, correct persona, policy, docs.
    """
    mock_session.agent_id = "agent-old"
    mock_session.code_state = "vulnerable"

    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    agent_id = await manager.ensure_agent(mock_session, vuln_config, "fixed")

    assert agent_id == "agent-123"  # new agent id from create
    assert mock_session.agent_id == "agent-123"
    assert mock_session.code_state == "fixed"
    mock_letta_client.delete_agent.assert_called_once_with("agent-old")
    mock_letta_client.create_agent.assert_called_once()
    mock_letta_client.update_agent.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_agent_noop_when_code_state_unchanged(mock_letta_client, mock_vuln_loader, mock_settings, vuln_config, mock_session):
    """Test: ensure_agent returns existing agent_id when code_state hasn't changed."""
    mock_session.agent_id = "agent-123"
    mock_session.code_state = "vulnerable"

    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    agent_id = await manager.ensure_agent(mock_session, vuln_config, "vulnerable")

    assert agent_id == "agent-123"
    mock_letta_client.create_agent.assert_not_called()
    mock_letta_client.update_agent.assert_not_called()


@pytest.mark.asyncio
async def test_get_config_for_vuln_vulnerable(mock_letta_client, mock_vuln_loader, mock_settings, vuln_config):
    """Test: get_config_for_vuln returns correct config for vulnerable state."""
    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    with patch.object(manager.vuln_loader, "get_vulnerable_config", return_value=vuln_config):
        config = await manager.get_config_for_vuln(2026, "llm01_test", "vulnerable")
    assert config.system_prompt == "You are a test assistant."
    assert config.canary is False


@pytest.mark.asyncio
async def test_get_config_for_vuln_fixed(mock_letta_client, mock_vuln_loader, mock_settings, fixed_config):
    """Test: get_config_for_vuln returns correct config for fixed state."""
    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    with patch.object(manager.vuln_loader, "get_fixed_config", return_value=fixed_config):
        config = await manager.get_config_for_vuln(2026, "llm01_test", "fixed")
    assert config.system_prompt == "You are a hardened assistant. CANARY-abc123"
    assert config.canary is True
    assert config.content_validation is True


@pytest.mark.asyncio
async def test_get_config_for_vuln_invalid_state(mock_letta_client, mock_vuln_loader, mock_settings):
    """Test: get_config_for_vuln raises ValueError for invalid code_state."""
    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    with pytest.raises(ValueError, match="Invalid code_state"):
        await manager.get_config_for_vuln(2026, "llm01_test", "broken")


@pytest.mark.asyncio
async def test_get_config_for_vuln_missing_config(mock_letta_client, mock_vuln_loader, mock_settings):
    """Test: get_config_for_vuln raises ValueError when config not found."""
    manager = AgentManager(mock_letta_client, mock_vuln_loader, mock_settings)
    with patch.object(manager.vuln_loader, "get_vulnerable_config", return_value=None):
        with pytest.raises(ValueError, match="No vulnerable config found"):
            await manager.get_config_for_vuln(2026, "nonexistent", "vulnerable")


def test_vuln_config_to_agent_config_conversion(vuln_config, mock_settings):
    """Test: _vuln_config_to_agent_config correctly converts dict policy to PolicyConfig."""
    agent_config = AgentManager._vuln_config_to_agent_config(vuln_config, mock_settings)
    assert agent_config.system_prompt == vuln_config.system_prompt
    assert agent_config.tools == vuln_config.tools
    assert agent_config.canary == vuln_config.canary
    assert agent_config.content_validation == vuln_config.content_validation
    assert agent_config.policy.denied_tools == []
    assert agent_config.policy.rules == []
    assert agent_config.policy.defaults == {"action": "allow"}
    assert agent_config.model == "ollama/nemotron-3-nano:4b"
    assert agent_config.embedding == "ollama/embeddinggemma:latest"
    assert agent_config.model_settings.provider_type == "ollama"
    assert agent_config.model_settings.temperature == 0.0
