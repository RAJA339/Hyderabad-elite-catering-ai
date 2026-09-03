"""LangFuse tracing when configured; structured log spans otherwise."""
from __future__ import annotations

import time
from contextlib import contextmanager

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("rag.trace")
_lf = None


def _langfuse():
    global _lf
    s = get_settings()
    if _lf is None and s.langfuse_public_key and s.langfuse_secret_key:
        try:
            from langfuse import Langfuse  # type: ignore

            _lf = Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key, host=s.langfuse_host)
        except Exception:  # noqa: BLE001
            _lf = False
    return _lf or None


@contextmanager
def span(name: str, **attrs):
    t0 = time.perf_counter()
    lf = _langfuse()
    trace = lf.trace(name=name, metadata=attrs) if lf else None
    try:
        yield trace
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        log.info("span", name=name, latency_ms=ms, **{k: v for k, v in attrs.items() if isinstance(v, (str, int, float, bool))})
        if trace:
            trace.update(output={"latency_ms": ms})
