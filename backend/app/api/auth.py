"""Authentication endpoints.

JWT-based auth with bcrypt password hashing. JWT is stored in an httpOnly
cookie (not localStorage) to prevent token theft via XSS — the secure pattern
a security teaching app should model.

Includes:
  - GET  /auth/setup-status — check if first-run registration is needed
  - POST /auth/register     — create the initial admin account (only when zero users)
  - POST /auth/login        — authenticate, set httpOnly cookie
  - POST /auth/logout       — clear the cookie
  - GET  /auth/me           — return current authenticated user
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SetupStatus,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT — auto_error=False so we can read the cookie ourselves
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# Cookie name
COOKIE_NAME = "epsilon_token"

# Rate limiting — in-memory, per IP
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 5


def _check_rate_limit(client_ip: str) -> None:
    """Check if the IP has exceeded the login rate limit."""
    now = time.time()
    attempts = _login_attempts[client_ip]
    # Prune old attempts
    _login_attempts[client_ip] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[client_ip]) >= _RATE_LIMIT_MAX:
        logger.warning(f"Rate limit hit for login from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {_RATE_LIMIT_WINDOW} seconds.",
        )
    _login_attempts[client_ip].append(now)


def _create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the JWT as an httpOnly cookie with SameSite=strict."""
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=not settings.DEV_MODE,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear the auth cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT (from Authorization header or cookie) and return the User model."""
    # Try Authorization header first, then cookie
    if token is None:
        token = request.cookies.get(COOKIE_NAME)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Check if first-run setup is needed (no users exist)."""
    result = await db.execute(select(func.count()).select_from(User).limit(1))
    user_count = result.scalar()
    return SetupStatus(needs_setup=user_count == 0)


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create the initial admin account. Only available when zero users exist."""
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    # Check that no users exist
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration is not available. An admin account already exists.",
        )

    user = User(username=body.username, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()

    token = _create_access_token({"sub": user.username, "uid": user.id})
    _set_auth_cookie(response, token)
    logger.info(f"Registered initial admin user '{body.username}'")
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and set JWT as httpOnly cookie."""
    _check_rate_limit(request.client.host if request.client else "unknown")

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = _create_access_token({"sub": user.username, "uid": user.id})
    _set_auth_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    _clear_auth_cookie(response)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user."""
    return UserResponse(id=current_user.id, username=current_user.username)
