"""Session model for Epsilon.

Letta owns the message store. This model does NOT duplicate messages —
it tracks which agent, which vulnerability, and which code state is
active. The frontend fetches messages from Letta via the backend proxy.

When a student toggles between "vulnerable" and "fixed" code states, the
agent_manager service calls `client.agents.modify()` to update the agent
in place (swap system prompt, tool list, policy) while preserving the
agent ID, memory blocks, and conversation history. This Session row
records the current state so the backend knows which config is active
without querying Letta.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Session(Base):
    """Tracks the active agent + vulnerability + code state for a student session.

    Attributes:
        id: UUID4 primary key (generated client-side, stored as string).
        agent_id: The LettaLocal agent ID this session is bound to.
        vulnerability_id: The vulnerability being studied, e.g.
            "llm01_prompt_injection".
        code_state: Which code variant is active — "vulnerable" or "fixed".
        created_at: UTC timestamp of session creation (server-side default).
        updated_at: UTC timestamp of last update (server-side onupdate).
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vulnerability_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="vulnerable",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
