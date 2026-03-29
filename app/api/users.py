"""User account management and authentication API."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    generate_token,
    hash_password,
    hash_token,
    require_admin,
    require_token,
    verify_password,
)
from app.database import get_session
from app.models import ApiToken, User

log = logging.getLogger("tinysignage.users")

router = APIRouter()

VALID_ROLES = ("admin", "editor", "viewer")
SESSION_EXPIRY_DAYS = 30


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


@router.post("/auth/login")
async def login(body: dict, session: AsyncSession = Depends(get_session)):
    """Authenticate with username/password, returns a session token."""
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalars().first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Create a session token
    plaintext = generate_token()
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=SESSION_EXPIRY_DAYS)
    token = ApiToken(
        token_hash=hash_token(plaintext),
        name=f"Session: {user.username}",
        role=user.role,
        user_id=user.id,
        created_by="login",
        expires_at=expires,
    )
    session.add(token)

    # Update last_login
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()

    log.info("User %s logged in", user.username)

    return {
        "token": plaintext,
        "user": _user_dict(user),
    }


@router.post("/auth/logout")
async def logout(
    token: ApiToken = Depends(require_token),
    session: AsyncSession = Depends(get_session),
):
    """Invalidate the current session token."""
    token.is_active = False
    await session.commit()
    return {"ok": True}


@router.get("/auth/me")
async def get_current_user(
    token: ApiToken = Depends(require_token),
    session: AsyncSession = Depends(get_session),
):
    """Get the currently authenticated user's info."""
    if token.user_id:
        user = await session.get(User, token.user_id)
        if user:
            return _user_dict(user)
    # API token without user — return token info
    return {
        "id": None,
        "username": token.name,
        "display_name": token.name,
        "role": token.role,
        "is_active": True,
        "created_at": token.created_at.isoformat() if token.created_at else None,
        "last_login": None,
    }


@router.get("/users")
async def list_users(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List all user accounts (admin only)."""
    result = await session.execute(select(User).order_by(User.created_at))
    return [_user_dict(u) for u in result.scalars().all()]


@router.post("/users", status_code=201)
async def create_user(
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new user account (admin only)."""
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "viewer")
    display_name = body.get("display_name", "").strip() or None

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(VALID_ROLES)}")

    # Check uniqueness
    existing = await session.execute(
        select(User).where(User.username == username)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    log.info("User %s created with role %s", username, role)
    return _user_dict(user)


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: dict,
    admin_token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update a user account (admin only)."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "display_name" in body:
        user.display_name = body["display_name"].strip() or None

    if "role" in body:
        new_role = body["role"]
        if new_role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(VALID_ROLES)}")
        # Prevent removing the last admin
        if user.role == "admin" and new_role != "admin":
            result = await session.execute(
                select(User).where(User.role == "admin", User.is_active == True)
            )
            admin_count = len(result.scalars().all())
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last admin user")
        user.role = new_role

    if "is_active" in body:
        # Prevent disabling the last admin
        if user.role == "admin" and not body["is_active"]:
            result = await session.execute(
                select(User).where(User.role == "admin", User.is_active == True)
            )
            admin_count = len(result.scalars().all())
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot disable the last admin user")
        user.is_active = body["is_active"]

    if "password" in body:
        password = body["password"]
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        user.password_hash = hash_password(password)

    await session.commit()
    await session.refresh(user)

    log.info("User %s updated", user.username)
    return _user_dict(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Delete a user account (admin only)."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting the last admin
    if user.role == "admin":
        result = await session.execute(
            select(User).where(User.role == "admin", User.is_active == True)
        )
        admin_count = len(result.scalars().all())
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin user")

    await session.delete(user)
    await session.commit()

    log.info("User %s deleted", user.username)
    return {"ok": True}
