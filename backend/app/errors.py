"""Error sanitization — prevent internal exception details from leaking to clients.

Two tiers:
  - sanitize_error_detail(): generic message for 500s (internal errors)
  - safe_error(): pass through user-actionable HTTPExceptions, sanitize the rest
"""

from __future__ import annotations

from fastapi import HTTPException


def sanitize_error_detail(e: Exception) -> str:
    """Return a safe error message for 500s — doesn't leak internals."""
    return "An internal error occurred. Check server logs for details."


def safe_error(e: Exception) -> str:
    """Pass through user-actionable errors, sanitize internal ones.

    HTTPException is how FastAPI raises 404/400/422 — those details
    are safe to show the client. Everything else gets sanitized.
    """
    if isinstance(e, HTTPException):
        return str(e.detail)
    return sanitize_error_detail(e)
