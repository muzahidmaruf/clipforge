"""
Supabase JWT verification.

Supabase issues HS256-signed JWTs. We verify them using the project's
JWT secret (Project Settings → API → JWT Secret).

If SUPABASE_JWT_SECRET is unset we fall back to *unverified* decoding —
useful only for local development. Production must set the secret.
"""

import os
import time
from typing import Optional

import jwt as pyjwt
from fastapi import Header, HTTPException, status

SUPABASE_URL          = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWT_SECRET   = os.getenv("SUPABASE_JWT_SECRET", "").strip()
REQUIRE_AUTH          = os.getenv("REQUIRE_AUTH", "true").strip().lower() not in ("0", "false", "no")


def _decode(token: str) -> dict:
    """Decode and validate a Supabase JWT. Raises HTTPException on failure."""
    try:
        if SUPABASE_JWT_SECRET:
            payload = pyjwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                # Supabase tokens have aud="authenticated"
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        else:
            # Dev fallback: trust the token without signature check.
            # Still enforce expiry + required claims.
            payload = pyjwt.decode(
                token,
                options={"verify_signature": False, "require": ["exp", "sub"]},
            )
            if payload.get("exp", 0) < time.time():
                raise pyjwt.ExpiredSignatureError()
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

class AuthUser:
    """Lightweight user wrapper exposed to route handlers."""
    __slots__ = ("id", "email", "claims")

    def __init__(self, claims: dict):
        self.id     = claims["sub"]
        self.email  = claims.get("email") or ""
        self.claims = claims

    def __repr__(self) -> str:
        return f"<AuthUser id={self.id} email={self.email!r}>"


def require_user(authorization: Optional[str] = Header(default=None)) -> AuthUser:
    """FastAPI dependency. Raises 401 if missing / invalid Authorization header."""
    if not REQUIRE_AUTH:
        # Disabled for local dev — return a fixed anonymous user
        return AuthUser({"sub": "00000000-0000-0000-0000-000000000000", "email": "anon@local"})

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    payload = _decode(token)
    return AuthUser(payload)


def optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[AuthUser]:
    """Like require_user but returns None instead of raising when missing."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        return AuthUser(_decode(authorization.split(" ", 1)[1].strip()))
    except HTTPException:
        return None
