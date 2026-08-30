"""Sessions unique constraint on (user_id, vulnerability_id).

VULN-004 (security review 2026-08-29): two concurrent first-messages
for the same user+vulnerability both inserted duplicate session rows;
every later request 500s on scalar_one_or_none. This migration adds
the DB-level guarantee (the per-user in-flight guard in agent.py
blocks the race at the API layer; this is defense in depth for any
future code path).

Dedup FIRST: existing deployments may already hold duplicates. Keeps
the OLDEST row per (user_id, vulnerability_id) — created_at is the
natural "first session" semantic; any duplicate-creation path that
did not immediately 500 would have accumulated history on the
earlier row. Tiebreak: minimum id for identical created_at.

NOTE: deleted duplicate rows may each reference their own Letta
agent; those agents orphan Letta-side. Acceptable for dev/teaching
stacks — manual cleanup via LettaLocal only if ever needed.

Safe on fresh databases: dedup deletes nothing, constraint applies
to the empty table trivially.

Revision ID: 003
Revises: 002
Create Date: 2026-08-30
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep-OLDEST dedup: delete every row that has a strictly OLDER twin.
# Survivor = the row with no older twin = the OLDEST per pair.
_DEDUP_SQL = """
DELETE FROM sessions s
WHERE EXISTS (
    SELECT 1 FROM sessions older
    WHERE older.user_id = s.user_id
      AND older.vulnerability_id = s.vulnerability_id
      AND (older.created_at < s.created_at
           OR (older.created_at = s.created_at
               AND older.id < s.id))
)
"""


def upgrade() -> None:
    op.execute(_DEDUP_SQL)
    op.create_unique_constraint(
        "uq_sessions_user_vuln", "sessions", ["user_id", "vulnerability_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sessions_user_vuln", "sessions", type_="unique")
