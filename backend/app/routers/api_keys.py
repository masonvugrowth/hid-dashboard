"""
API Keys router — admin-only CRUD for managing external API keys.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.api_key import ApiKey
from app.routers.auth import require_admin
from app.models.user import User

router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────────

def _generate_api_key() -> str:
    """Generate a random API key with 'hid_' prefix."""
    return "hid_" + secrets.token_urlsafe(32)


def _hash_key(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _key_out(k: ApiKey) -> dict:
    return {
        "id": str(k.id),
        "name": k.name,
        "key_prefix": k.key_prefix,
        "is_active": k.is_active,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_by": str(k.created_by) if k.created_by else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateKeyIn(BaseModel):
    name: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("")
def create_api_key(
    body: CreateKeyIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a new API key. The plaintext key is returned ONCE — store it safely."""
    try:
        plain_key = _generate_api_key()
        key_prefix = plain_key[:12]

        api_key = ApiKey(
            name=body.name.strip(),
            key_hash=_hash_key(plain_key),
            key_prefix=key_prefix,
            created_by=admin.id,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        result = _key_out(api_key)
        result["key"] = plain_key  # Only time the full key is returned

        return {
            "success": True,
            "data": result,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_api_keys(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all API keys (active and inactive)."""
    try:
        keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
        return {
            "success": True,
            "data": [_key_out(k) for k in keys],
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke (soft-delete) an API key."""
    try:
        api_key = db.query(ApiKey).filter_by(id=key_id).first()
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        api_key.is_active = False
        api_key.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "success": True,
            "data": {"revoked": str(key_id)},
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
