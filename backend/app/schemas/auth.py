from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Credentials submitted by a user to obtain an access token."""

    username: str = Field(
        ...,
        description="The user's username.",
    )
    password: str = Field(
        ...,
        description="The user's password.",
    )


class RegisterRequest(BaseModel):
    """Credentials for first-run admin registration."""

    username: str = Field(
        ...,
        description="The desired username (3-50 chars, alphanumeric + underscore).",
    )
    password: str = Field(
        ...,
        description="The desired password (min 8 chars).",
    )
    confirm_password: str = Field(
        ...,
        description="Must match password.",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3-50 characters")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must contain only letters, numbers, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    """An OAuth2-style bearer token response."""

    access_token: str = Field(
        ...,
        description="The JWT (or opaque) access token issued upon successful authentication.",
    )
    token_type: str = Field(
        default="bearer",
        description="The type of token issued (default: 'bearer').",
    )


class UserResponse(BaseModel):
    """Public representation of an authenticated user."""

    id: int = Field(
        ...,
        description="The unique numeric identifier of the user.",
    )
    username: str = Field(
        ...,
        description="The user's display name / login handle.",
    )


class SetupStatus(BaseModel):
    """Response from /auth/setup-status indicating whether first-run setup is needed."""

    needs_setup: bool = Field(
        ...,
        description="True if no users exist and registration is available.",
    )
