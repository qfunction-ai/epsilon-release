"""Async SQLAlchemy database setup for Epsilon.

Provides the async engine, session maker, declarative base, and the
get_db() FastAPI dependency. Follows Delta's lazy-initialization pattern
to avoid opening connection pools at import time.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy engine / session maker
#
# Avoids import-time side effects (opening a connection pool when the module
# is imported). The engine is created on first access via _get_engine().
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Lazily create the async engine on first access."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        logger.info("Async engine created for %s", settings.DATABASE_URL)
    return _engine


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Lazily create the session maker on first access."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


# Declarative base for all models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically committed on success and rolled back
    on exception. The session is always closed in the finally block.
    """
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
