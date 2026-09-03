from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.core import db
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    tenant: str = "hec"


@router.post("/login")
async def login(body: LoginIn):
    row = await db.fetchrow(
        "SELECT u.id, u.tenant_id, u.role::text AS role, u.password_hash, u.full_name FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE t.slug = $1 AND u.email = $2 AND u.is_active",
        body.tenant, body.email)
    if not row or not row["password_hash"] or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "invalid credentials")
    await db.execute("UPDATE users SET last_login_at = now() WHERE id = $1", row["id"])
    return {"access_token": create_access_token(user_id=str(row["id"]), tenant_id=str(row["tenant_id"]), role=row["role"]),
            "role": row["role"], "name": row["full_name"]}
