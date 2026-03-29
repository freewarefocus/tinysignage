"""Token management API — admin-only CRUD for API tokens."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record as audit
from app.auth import generate_token, hash_token, require_admin
from app.database import get_session
from app.models import ApiToken, Device

router = APIRouter()


@router.post("/tokens", status_code=201)
async def create_token(
    body: dict,
    request: Request,
    admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new API token. Returns plaintext token once — it is never stored."""
    name = body.get("name")
    role = body.get("role")  # "admin" or "device"
    if not name or role not in ("admin", "device"):
        raise HTTPException(status_code=400, detail="name and role (admin|device) required")

    device_id = body.get("device_id")
    if role == "device":
        if not device_id:
            raise HTTPException(status_code=400, detail="device_id required for device tokens")
        device = await session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

    plaintext = generate_token()
    token = ApiToken(
        token_hash=hash_token(plaintext),
        name=name,
        role=role,
        device_id=device_id if role == "device" else None,
        created_by=admin.name,
        expires_at=None,
    )
    session.add(token)
    await session.flush()
    await audit(session, action="create", entity_type="token", entity_id=token.id,
                details={"name": name, "role": role}, token=admin, request=request)
    await session.commit()
    await session.refresh(token)

    return {
        "id": token.id,
        "token": plaintext,  # Shown once, never stored
        "name": token.name,
        "role": token.role,
        "device_id": token.device_id,
        "created_at": token.created_at.isoformat() if token.created_at else None,
    }


@router.get("/tokens")
async def list_tokens(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List all tokens (masked — no plaintext)."""
    result = await session.execute(select(ApiToken).order_by(ApiToken.created_at.desc()))
    tokens = result.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "role": t.role,
            "device_id": t.device_id,
            "is_active": t.is_active,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Revoke (deactivate) a token."""
    token = await session.get(ApiToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    token.is_active = False
    await audit(session, action="revoke", entity_type="token", entity_id=token_id,
                details={"name": token.name}, token=_admin, request=request)
    await session.commit()
    return {"ok": True}
