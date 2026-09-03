"""JWT for staff, HMAC tokens for magic links / portal sessions, OTP hashing, RBAC."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import get_settings

ALGO = "HS256"
BCRYPT_MAX_BYTES = 72  # bcrypt hard limit; longer input raises rather than truncating

ROLE_RANK = {"viewer": 0, "kitchen": 1, "sales": 2, "manager": 3, "owner": 4}


def _pw_bytes(p: str) -> bytes:
    return p.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(p: str) -> str:
    """bcrypt directly rather than through passlib, whose bcrypt backend breaks against
    bcrypt >= 4.1 and takes password verification down with it."""
    return bcrypt.hashpw(_pw_bytes(p), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(p), h.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(*, user_id: str, tenant_id: str, role: str, hours: int = 12) -> str:
    now = datetime.now(UTC)
    payload = {"sub": user_id, "tid": tenant_id, "role": role, "iat": now, "exp": now + timedelta(hours=hours)}
    return jwt.encode(payload, get_settings().app_secret, algorithm=ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().app_secret, algorithms=[ALGO])
    except JWTError as e:  # pragma: no cover
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from e


class Principal:
    def __init__(self, user_id: str, tenant_id: str, role: str):
        self.user_id, self.tenant_id, self.role = user_id, tenant_id, role


async def current_principal(request: Request) -> Principal:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    data = decode_token(auth.split(" ", 1)[1])
    return Principal(data["sub"], data["tid"], data["role"])


def require_role(*roles: str):
    allowed: Iterable[str] = roles

    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.role not in allowed and ROLE_RANK.get(p.role, -1) < max(ROLE_RANK[r] for r in allowed):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return p

    return _dep


# ── Opaque tokens (magic links, portal sessions, share links) ────────────────
def new_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hmac.new(get_settings().app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
