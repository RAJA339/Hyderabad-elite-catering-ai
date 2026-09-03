from fastapi import APIRouter

from app.core import db
from app.core.cache import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    out = {"status": "ok", "db": False, "redis": False}
    try:
        out["db"] = (await db.fetchval("SELECT 1")) == 1
    except Exception:  # noqa: BLE001
        pass
    try:
        out["redis"] = await get_redis().ping()
    except Exception:  # noqa: BLE001
        pass
    return out
