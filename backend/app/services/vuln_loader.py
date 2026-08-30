"""Vulnerability config loader — reads vulns/ directory and serves configs via API.

Vulnerabilities are data, not code. Each vulnerability is a directory under
vulns/{year}/ containing YAML configs, code snippets, and RAG documents.
This loader reads them at startup and caches in memory.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.schemas.vulnerability import (
    CodeComparison,
    DefenseRef,
    ExploitStep,
    OwaspStrategy,
    VulnerabilityConfig,
    VulnerabilityDetail,
    VulnerabilitySummary,
    YearInfo,
)

logger = logging.getLogger(__name__)


class VulnLoader:
    """Loads vulnerability configs from the vulns/ directory.

    Usage:
        loader = VulnLoader()
        loader.load()
        years = loader.get_years()
        vuln = loader.get_vulnerability(2026, "llm01_prompt_injection")
    """

    def __init__(self, vulns_dir: str = "vulns"):
        # Resolve vulns directory — check multiple candidate locations:
        # 1. Relative to project root (../../vulns from backend/app/) — dev mode
        # 2. /app/vulns — Docker (vulns mounted at /app/vulns)
        # 3. ./vulns — fallback relative to cwd
        app_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        candidates = [
            app_dir.parent / vulns_dir,     # dev: epsilon/vulns (repo root,
                                            # one level above backend/ — the
                                            # old candidate (app_dir/vulns =
                                            # backend/vulns) never existed;
                                            # host runs never hit it because
                                            # everything was containerized)
            Path("/app") / vulns_dir,       # docker: /app/vulns
            Path.cwd() / vulns_dir,          # fallback: cwd/vulns
        ]
        for candidate in candidates:
            if candidate.exists():
                self.vulns_dir = candidate
                break
        else:
            self.vulns_dir = candidates[0]  # will log warning in load()
        self._years: dict[int, YearInfo] = {}
        self._vulns: dict[tuple[int, str], VulnerabilityDetail] = {}
        self._vuln_configs: dict[tuple[int, str, str], VulnerabilityConfig] = {}
        self._code_comparisons: dict[tuple[int, str], CodeComparison] = {}

    def load(self) -> None:
        """Scan all year directories, read index.yaml per year, read config.yaml per vulnerability."""
        if not self.vulns_dir.exists():
            logger.warning(f"Vulns directory not found: {self.vulns_dir}")
            return

        for year_dir in sorted(self.vulns_dir.iterdir(), reverse=True):
            if not year_dir.is_dir() or year_dir.name.startswith("."):
                continue

            try:
                year = int(year_dir.name)
            except ValueError:
                continue

            index_path = year_dir / "index.yaml"
            if not index_path.exists():
                logger.warning(f"No index.yaml in {year_dir}")
                continue

            with open(index_path) as f:
                index_data = yaml.safe_load(f)

            if not index_data:
                continue

            entries = []
            for entry in index_data.get("entries", []):
                vuln_id = entry["id"]
                vuln_dir = year_dir / vuln_id

                # Load config.yaml for detail
                detail = self._load_config(vuln_dir, entry)
                if detail is not None:
                    self._vulns[(year, vuln_id)] = detail
                    entries.append(
                        VulnerabilitySummary(
                            id=vuln_id,
                            owasp_id=entry["owasp_id"],
                            title=entry["title"],
                            year=year,
                            has_runtime_defense=detail.defense_refs is not None and len(detail.defense_refs) > 0,
                            defense_summary=self._defense_summary(detail),
                        )
                    )

                # Load vulnerable.yaml and fixed.yaml
                vuln_config = self._load_vuln_config(vuln_dir, "vulnerable.yaml")
                if vuln_config:
                    self._vuln_configs[(year, vuln_id, "vulnerable")] = vuln_config

                fixed_config = self._load_vuln_config(vuln_dir, "fixed.yaml")
                if fixed_config:
                    self._vuln_configs[(year, vuln_id, "fixed")] = fixed_config

                # Load code comparison
                code = self._load_code_comparison(vuln_dir)
                if code:
                    self._code_comparisons[(year, vuln_id)] = code

            year_info = YearInfo(
                year=year,
                latest=index_data.get("latest", False),
                edition=index_data.get("edition", ""),
                entries=entries,
            )
            self._years[year] = year_info

        logger.info(f"Loaded {len(self._vulns)} vulnerabilities across {len(self._years)} years")

    def _load_config(self, vuln_dir: Path, entry: dict) -> VulnerabilityDetail | None:
        """Load config.yaml for a vulnerability."""
        config_path = vuln_dir / "config.yaml"
        if not config_path.exists():
            logger.warning(f"No config.yaml in {vuln_dir}")
            return None

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        defense_refs = []
        for ref in data.get("defense_refs", []):
            strategies = []
            for s in ref.get("owasp_strategies", []):
                if isinstance(s, dict):
                    strategies.append(OwaspStrategy(
                        number=s.get("number", 0),
                        title=s.get("title", ""),
                        description=s.get("description", ""),
                    ))
                elif isinstance(s, str):
                    # Backward compat: old format used bare "#4" strings
                    num = int(s.lstrip("#"))
                    strategies.append(OwaspStrategy(number=num, title="", description=""))

            defense_refs.append(
                DefenseRef(
                    control=ref.get("control", ""),
                    owasp_strategies=strategies,
                    implementation=ref.get("implementation", ref.get("description", "")),
                    code_snippet=ref.get("code_snippet", ""),
                )
            )

        # Parse exploit steps
        exploit_steps = []
        for step in data.get("exploit_steps", []):
            exploit_steps.append(ExploitStep(
                title=step.get("title", ""),
                instruction=step.get("instruction", ""),
                prompt=step.get("prompt", ""),
            ))

        return VulnerabilityDetail(
            id=entry["id"],
            owasp_id=entry["owasp_id"],
            title=entry["title"],
            year=int(vuln_dir.parent.name),
            has_runtime_defense=len(defense_refs) > 0,
            defense_summary=self._defense_summary_from_refs(defense_refs),
            description=data.get("description", ""),
            real_world_examples=data.get("real_world_examples", []),
            why_it_matters=data.get("why_it_matters", ""),
            suggested_prompts=data.get("suggested_prompts", []),
            exploit_steps=exploit_steps,
            defense_refs=defense_refs,
        )

    def _load_vuln_config(self, vuln_dir: Path, filename: str) -> VulnerabilityConfig | None:
        """Load vulnerable.yaml or fixed.yaml."""
        config_path = vuln_dir / filename
        if not config_path.exists():
            return None

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        return VulnerabilityConfig(
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            policy=data.get("policy", {}),
            canary=data.get("canary", False),
            canary_value=data.get("canary_value"),
            content_validation=data.get("content_validation", False),
            documents=data.get("documents", []),
        )

    def _load_code_comparison(self, vuln_dir: Path) -> CodeComparison | None:
        """Load vulnerable_code and fixed_code as text (no extension)."""
        vuln_code_path = vuln_dir / "vulnerable_code"
        fixed_code_path = vuln_dir / "fixed_code"

        if not vuln_code_path.exists() and not fixed_code_path.exists():
            return None

        vuln_code = vuln_code_path.read_text() if vuln_code_path.exists() else ""
        fixed_code = fixed_code_path.read_text() if fixed_code_path.exists() else ""

        return CodeComparison(vulnerable_code=vuln_code, fixed_code=fixed_code)

    def _defense_summary(self, detail: VulnerabilityDetail) -> str:
        """Generate a short defense summary from defense_refs."""
        if not detail.defense_refs:
            return "No runtime defense"
        controls = [ref.control for ref in detail.defense_refs]
        return ", ".join(controls)

    def _defense_summary_from_refs(self, refs: list[DefenseRef]) -> str:
        if not refs:
            return "No runtime defense"
        controls = [ref.control for ref in refs]
        return ", ".join(controls)

    def get_years(self) -> list[YearInfo]:
        """Return all available years sorted descending."""
        return sorted(self._years.values(), key=lambda y: y.year, reverse=True)

    def get_year(self, year: int) -> YearInfo | None:
        """Return year metadata."""
        return self._years.get(year)

    def get_vulnerabilities(self, year: int) -> list[VulnerabilitySummary]:
        """Return all vulnerability summaries for a year."""
        year_info = self._years.get(year)
        if year_info is None:
            return []
        return year_info.entries

    def get_vulnerability(self, year: int, vuln_id: str) -> VulnerabilityDetail | None:
        """Return single vulnerability detail."""
        return self._vulns.get((year, vuln_id))

    def get_vulnerable_config(self, year: int, vuln_id: str) -> VulnerabilityConfig | None:
        """Return the vulnerable agent config for a vulnerability."""
        return self._vuln_configs.get((year, vuln_id, "vulnerable"))

    def get_fixed_config(self, year: int, vuln_id: str) -> VulnerabilityConfig | None:
        """Return the fixed agent config for a vulnerability."""
        return self._vuln_configs.get((year, vuln_id, "fixed"))

    def get_code_comparison(self, year: int, vuln_id: str) -> CodeComparison | None:
        """Return code comparison for a vulnerability."""
        return self._code_comparisons.get((year, vuln_id))

    def get_vuln_dir(self, year: int, vuln_id: str) -> Path:
        """Return the directory path for a vulnerability."""
        return self.vulns_dir / str(year) / vuln_id
