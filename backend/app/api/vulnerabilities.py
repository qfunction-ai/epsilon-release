"""Vulnerability listing endpoints.

Reads from the VulnLoader cached at startup. No database access needed —
vulnerability configs are static YAML files loaded from disk.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas.vulnerability import (
    CodeComparison,
    VulnerabilityDetail,
    YearInfo,
)

router = APIRouter()


def _get_loader(request: Request):
    return request.app.state.vuln_loader


@router.get("", response_model=list[YearInfo])
async def list_years(request: Request):
    """List all available OWASP edition years with their vulnerability summaries."""
    loader = _get_loader(request)
    return loader.get_years()


@router.get("/{year}", response_model=YearInfo)
async def get_year(request: Request, year: int):
    """Return metadata and vulnerability summaries for a specific year."""
    loader = _get_loader(request)
    year_info = loader.get_year(year)
    if year_info is None:
        raise HTTPException(status_code=404, detail=f"Year {year} not found")
    return year_info


@router.get("/{year}/{vuln_id}", response_model=VulnerabilityDetail)
async def get_vulnerability(request: Request, year: int, vuln_id: str):
    """Return full details for a specific vulnerability."""
    loader = _get_loader(request)
    vuln = loader.get_vulnerability(year, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=404, detail=f"Vulnerability {vuln_id} not found in {year}")
    return vuln


@router.get("/{year}/{vuln_id}/code", response_model=CodeComparison)
async def get_code_comparison(request: Request, year: int, vuln_id: str):
    """Return side-by-side vulnerable and fixed code for a vulnerability."""
    loader = _get_loader(request)
    code = loader.get_code_comparison(year, vuln_id)
    if code is None:
        raise HTTPException(status_code=404, detail=f"Code comparison not found for {vuln_id} in {year}")
    return code
