"""Vulns API integration: shapes and 404s from the real loader."""
from __future__ import annotations


def test_list_years(app_client):
    r = app_client.client.get("/vulns")
    assert r.status_code == 200
    years = r.json()
    assert any(y["year"] == 2026 for y in years)


def test_year_detail_and_vuln_detail(app_client):
    c = app_client.client
    y = c.get("/vulns/2026")
    assert y.status_code == 200
    d = c.get("/vulns/2026/llm01_prompt_injection")
    assert d.status_code == 200
    detail = d.json()
    assert detail["id"] == "llm01_prompt_injection"
    assert detail["suggested_prompts"]


def test_code_comparison_shape(app_client):
    r = app_client.client.get("/vulns/2026/llm01_prompt_injection/code")
    assert r.status_code == 200
    code = r.json()
    assert "vulnerable" in code or "vulnerable_code" in code


def test_unknown_vuln_404(app_client):
    r = app_client.client.get("/vulns/2026/llm99_nonexistent")
    assert r.status_code == 404


def test_unknown_year_404(app_client):
    r = app_client.client.get("/vulns/1999")
    assert r.status_code == 404
