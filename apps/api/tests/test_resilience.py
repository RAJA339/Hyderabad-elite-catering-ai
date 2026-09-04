"""A dead Redis, or any unhandled error, must not read to a browser as an unreachable API.

An exception escaping to Starlette's own error handler produces a response with no CORS
headers. The browser then refuses to expose it and `fetch` rejects, so the site reports
"the API is unreachable, or CORS is wrong" for what is really a server-side fault — which
is exactly how a missing Redis silently broke the deployed chat widget.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import cache
from app.main import _catch_unhandled

ORIGIN = "https://site.vercel.app"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("redis is not reachable")

    # Same order as app/main.py: CORS added last, so it wraps the catch-all.
    app.add_middleware(BaseHTTPMiddleware, dispatch=_catch_unhandled)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_still_carries_cors_headers(client):
    r = client.get("/boom", headers={"Origin": ORIGIN})
    assert r.status_code == 500
    # Without this header the browser reports a CORS failure instead of the real error.
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert "RuntimeError" in r.json()["detail"]


class _DeadRedis:
    """Mirrors the real failure: from_url() succeeds, the command raises on await."""

    def __getattr__(self, _name):
        async def _raise(*_a, **_k):
            raise ConnectionError("Error 111 connecting to localhost:6379. Connection refused.")

        return _raise


async def test_rate_limit_allows_when_redis_is_down(monkeypatch):
    monkeypatch.setattr(cache, "get_redis", lambda: _DeadRedis())
    cache._warned = False
    assert await cache.rate_limit("rl:chat:abc", 30, 60) is True


async def test_seen_once_treats_every_message_as_new_when_redis_is_down(monkeypatch):
    monkeypatch.setattr(cache, "get_redis", lambda: _DeadRedis())
    cache._warned = False
    # A duplicate reply is recoverable; dropping every WhatsApp message is not.
    assert await cache.seen_once("wa:msg:1") is True
