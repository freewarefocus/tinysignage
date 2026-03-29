"""API token authentication and user session auth for TinySignage."""

import hashlib
import secrets
import string
from datetime import datetime, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import ApiToken

TOKEN_PREFIX = "ts_"

_PAIRING_CHARS = string.ascii_uppercase + string.digits

# Role hierarchy: admin > editor > viewer
ROLE_HIERARCHY = {"admin": 3, "editor": 2, "viewer": 1, "device": 0}


def generate_token() -> str:
    """Generate a secure random token string with ts_ prefix."""
    return TOKEN_PREFIX + secrets.token_hex(24)


def hash_token(plaintext: str) -> str:
    """SHA-256 hex digest of a plaintext token."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def hash_password(plaintext: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


def generate_pairing_code() -> str:
    """Generate a 6-character uppercase alphanumeric pairing code."""
    return "".join(secrets.choice(_PAIRING_CHARS) for _ in range(6))


def hash_pairing_code(code: str) -> str:
    """SHA-256 hex digest of a pairing code (uppercased for consistency)."""
    return hashlib.sha256(code.upper().encode()).hexdigest()


async def _lookup_token(token_str: str, session: AsyncSession) -> ApiToken:
    """Look up a token by its hash. Raises 401 if invalid."""
    token_hash = hash_token(token_str)
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.is_active == True,
        )
    )
    api_token = result.scalars().first()
    if not api_token:
        raise HTTPException(status_code=401, detail="Invalid or inactive token")

    # Check expiration
    if api_token.expires_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if api_token.expires_at < now:
            raise HTTPException(status_code=401, detail="Token has expired")

    return api_token


def _extract_bearer(request: Request) -> str:
    """Extract Bearer token from Authorization header. Raises 401 if missing."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return auth[7:]


async def require_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ApiToken:
    """FastAPI dependency: require a valid Bearer token."""
    token_str = _extract_bearer(request)
    return await _lookup_token(token_str, session)


async def require_admin(
    token: ApiToken = Depends(require_token),
) -> ApiToken:
    """FastAPI dependency: require an admin token."""
    if token.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return token


async def require_editor(
    token: ApiToken = Depends(require_token),
) -> ApiToken:
    """FastAPI dependency: require editor or admin role."""
    if ROLE_HIERARCHY.get(token.role, 0) < ROLE_HIERARCHY["editor"]:
        raise HTTPException(status_code=403, detail="Editor access required")
    return token


async def require_viewer(
    token: ApiToken = Depends(require_token),
) -> ApiToken:
    """FastAPI dependency: require any authenticated user (viewer, editor, or admin)."""
    if ROLE_HIERARCHY.get(token.role, 0) < ROLE_HIERARCHY["viewer"]:
        raise HTTPException(status_code=403, detail="Login required")
    return token


async def require_device(
    token: ApiToken = Depends(require_token),
) -> ApiToken:
    """FastAPI dependency: require a device token. Returns the token (use .device_id)."""
    if token.role != "device":
        raise HTTPException(status_code=403, detail="Device token required")
    return token
