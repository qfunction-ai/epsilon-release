"""Unit tests for VulnLoader."""

from pathlib import Path

import pytest
import yaml

from app.services.vuln_loader import VulnLoader


@pytest.fixture
def vulns_dir(tmp_path: Path) -> Path:
    """Create a temp vulns directory with test configs."""
    # 2026 index
    year_dir = tmp_path / "2026"
    year_dir.mkdir()
    (year_dir / "index.yaml").write_text(yaml.dump({
        "year": 2026,
        "latest": True,
        "edition": "OWASP Top 10 for LLM Applications 2026",
        "entries": [
            {"id": "llm01_test", "owasp_id": "LLM01", "title": "Test Injection"},
            {"id": "llm02_test", "owasp_id": "LLM02", "title": "Test Info"},
        ],
    }))

    # llm01_test config
    vuln_dir = year_dir / "llm01_test"
    vuln_dir.mkdir()
    (vuln_dir / "config.yaml").write_text(yaml.dump({
        "id": "llm01_test",
        "description": "Test vulnerability for prompt injection.",
        "real_world_examples": ["EchoLeak (2025)"],
        "why_it_matters": "Prompt injection is the #1 risk.",
        "suggested_prompts": ["Ignore previous instructions"],
        "defense_refs": [
            {"control": "PolicyChecker", "owasp_strategies": ["#4"], "description": "Blocks tool calls"},
        ],
    }))
    (vuln_dir / "vulnerable.yaml").write_text(yaml.dump({
        "system_prompt": "You are a helpful assistant.",
        "tools": ["web_search"],
        "policy": {"denied_tools": [], "rules": [], "defaults": {"action": "allow"}},
        "canary": False,
        "content_validation": False,
        "documents": [],
    }))
    (vuln_dir / "fixed.yaml").write_text(yaml.dump({
        "system_prompt": "You are a helpful assistant. CANARY-abc123",
        "tools": ["web_search"],
        "policy": {"denied_tools": [], "rules": [{"name": "block-email", "condition": {"field": "tool_args.to", "operator": "matches", "value": "@evil"}, "action": "deny", "priority": 100}], "defaults": {"action": "deny"}},
        "canary": True,
        "content_validation": True,
        "documents": [],
    }))
    # Extensionless per the corpus convention (vulnerable_code / fixed_code).
    (vuln_dir / "vulnerable_code").write_text("# vulnerable code\npass\n")
    (vuln_dir / "fixed_code").write_text("# fixed code\npass\n")

    # llm02_test config (minimal — no defense refs)
    vuln2_dir = year_dir / "llm02_test"
    vuln2_dir.mkdir()
    (vuln2_dir / "config.yaml").write_text(yaml.dump({
        "id": "llm02_test",
        "description": "Test info disclosure.",
        "real_world_examples": [],
        "why_it_matters": "Data can leak.",
        "suggested_prompts": ["Show me the salary bands"],
        "defense_refs": [],
    }))

    return tmp_path


def test_load_parses_all_years_and_vulnerabilities(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    years = loader.get_years()
    assert len(years) == 1
    assert years[0].year == 2026


def test_get_years_returns_sorted_descending(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    years = loader.get_years()
    assert years[0].year == 2026  # Only one year, but sorted descending


def test_get_vulnerabilities_returns_correct_list(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    vulns = loader.get_vulnerabilities(2026)
    assert len(vulns) == 2
    assert vulns[0].id == "llm01_test"
    assert vulns[1].id == "llm02_test"


def test_get_vulnerability_returns_detail(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    vuln = loader.get_vulnerability(2026, "llm01_test")
    assert vuln is not None
    assert vuln.id == "llm01_test"
    assert vuln.owasp_id == "LLM01"
    assert vuln.title == "Test Injection"
    assert "Prompt injection is the #1 risk." in vuln.why_it_matters
    assert len(vuln.suggested_prompts) == 1
    assert len(vuln.defense_refs) == 1
    assert vuln.defense_refs[0].control == "PolicyChecker"


def test_get_vulnerable_config(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    config = loader.get_vulnerable_config(2026, "llm01_test")
    assert config is not None
    assert config.canary is False
    assert config.content_validation is False
    assert "allow" in str(config.policy.get("defaults", {}))


def test_get_fixed_config(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    config = loader.get_fixed_config(2026, "llm01_test")
    assert config is not None
    assert config.canary is True
    assert config.content_validation is True
    assert "deny" in str(config.policy.get("defaults", {}))


def test_get_code_comparison(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    code = loader.get_code_comparison(2026, "llm01_test")
    assert code is not None
    assert "vulnerable code" in code.vulnerable_code
    assert "fixed code" in code.fixed_code


def test_missing_files_return_none(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    # Non-existent vulnerability
    assert loader.get_vulnerability(2026, "nonexistent") is None
    assert loader.get_vulnerable_config(2026, "nonexistent") is None
    assert loader.get_fixed_config(2026, "nonexistent") is None
    assert loader.get_code_comparison(2026, "nonexistent") is None


def test_missing_year_returns_none(vulns_dir: Path):
    loader = VulnLoader(vulns_dir=str(vulns_dir))
    loader.load()
    assert loader.get_year(9999) is None
    assert loader.get_vulnerabilities(9999) == []
