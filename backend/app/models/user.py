"""User model for Epsilon.

Stores authentication credentials. Passwords are hashed with bcrypt
via passlib before being stored in `hashed_password`.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """Application user.

    Attributes:
        id: Auto-incrementing primary key.
        username: Unique username for login.
        hashed_password: bcrypt-hashed password (never store plaintext).
        created_at: UTC timestamp of account creation (server-side default).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
