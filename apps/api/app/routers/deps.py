from __future__ import annotations

from uuid import UUID

from fastapi import Depends

from app.core.config import get_settings
from app.core.security import Principal, current_principal, require_role
from app.leads.repository import tenant_id_for_slug


async def default_tenant() -> UUID:
    return await tenant_id_for_slug(get_settings().tenant_default_slug)


async def tenant_from_principal(p: Principal = Depends(current_principal)) -> UUID:
    return UUID(p.tenant_id)


staff = require_role("sales", "manager", "owner", "kitchen", "viewer")
manager = require_role("manager", "owner")
owner = require_role("owner")
