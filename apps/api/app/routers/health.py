import os

from fastapi import APIRouter

from app.core import db
from app.core.cache import get_redis
from app.core.config import get_settings
from app.notify.channels import owner_channels

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    # cors_origins is echoed because a browser blocked by CORS gets no readable error: this
    # is the only way to see, from a browser, the exact origin list the API is running with.
    st = get_settings()
    out = {"status": "ok", "db": False, "redis": False,
           "cors_origins": st.cors_origin_list, "llm_key_present": bool(st.anthropic_api_key or st.openai_api_key),
           "owner_channels": owner_channels(),
           # Railway sets this; it is the fastest way to tell whether the API is on the same commit as the site.
           "build": (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT") or "")[:7] or None}
    try:
        out["db"] = (await db.fetchval("SELECT 1")) == 1
    except Exception:  # noqa: BLE001
        pass
    try:
        out["redis"] = await get_redis().ping()
    except Exception:  # noqa: BLE001
        pass
    return out
