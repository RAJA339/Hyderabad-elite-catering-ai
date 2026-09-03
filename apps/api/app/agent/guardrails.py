"""Output guardrails: every rupee figure in the reply must trace back to a tool result this
turn (or the session state); guest caps; length; no competitor names."""
from __future__ import annotations

import re

RUPEE = re.compile(r"₹\s?([\d,]+(?:\.\d{1,2})?)|(?:rs\.?|rupees)\s?([\d,]+(?:\.\d{1,2})?)", re.I)
COMPETITORS = ("pista house", "paradise", "bawarchi", "shah ghouse", "cafe bahar", "meridian")


def _numbers_in(obj) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _numbers_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _numbers_in(v)
    elif isinstance(obj, (int, float)):
        out.add(_norm(str(obj)))
    elif isinstance(obj, str):
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", obj):
            out.add(_norm(m.group(0)))
    return out


def _norm(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def check_reply(reply: str, tool_results: list, session_state: dict, *, max_guests: int = 500) -> tuple[str, list[str]]:
    """Return (possibly amended reply, list of violations)."""
    allowed = _numbers_in(tool_results) | _numbers_in(session_state)
    violations: list[str] = []
    for m in RUPEE.finditer(reply):
        raw = m.group(1) or m.group(2)
        if _norm(raw) not in allowed:
            violations.append(f"ungrounded_amount:{raw}")
    if violations:
        # Strip the ungrounded amounts rather than sending invented prices
        reply = RUPEE.sub(lambda m: m.group(0) if _norm(m.group(1) or m.group(2)) in allowed else "(price on request)", reply)
    low = reply.lower()
    for c in COMPETITORS:
        if c in low:
            violations.append(f"competitor_mention:{c}")
            reply = re.sub(re.escape(c), "other caterers", reply, flags=re.I)
    if re.search(r"\b(5[0-9]{2}|[6-9][0-9]{2}|\d{4,})\s*guests", low):
        n = int(re.search(r"(\d+)\s*guests", low).group(1))
        if n > max_guests and "two sittings" not in low and "500" not in reply:
            violations.append("guest_cap_not_communicated")
    return reply, violations
