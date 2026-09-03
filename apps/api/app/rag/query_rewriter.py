"""Query understanding: intent + structured filters. Fast heuristics first; an LLM refines
when available. Output feeds metadata pre-filtering and tool routing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENTS = ("menu", "pricing", "policy", "festival", "faq", "modification", "booking", "smalltalk", "escalation")

_GUESTS = re.compile(r"(\d{2,3})\s*(?:guests?|people|pax|members|persons|mandi|janalu)", re.I)
_FESTIVAL_WORDS = {
    "diwali": "diwali", "deepavali": "diwali", "dasara": "dasara", "dussehra": "dasara", "bathukamma": "bathukamma",
    "ganesh": "ganesh_chaturthi", "vinayaka": "ganesh_chaturthi", "sankranti": "sankranti", "pongal": "sankranti",
    "ugadi": "ugadi", "ramzan": "ramzan", "ramadan": "ramzan", "eid": "ramzan", "iftar": "ramzan", "bakrid": "bakrid",
    "christmas": "christmas", "new year": "new_year", "bonalu": "bonalu", "holi": "holi", "wedding": "wedding_season",
}


@dataclass
class QueryPlan:
    raw: str
    rewritten: str
    intent: str = "faq"
    diet: str | None = None
    guest_count: int | None = None
    festival_keys: list[str] = field(default_factory=list)
    price_band: str | None = None
    needs_live_prices: bool = False
    needs_retrieval: bool = True
    source_types: list[str] = field(default_factory=list)


def heuristic_plan(text: str) -> QueryPlan:
    t = text.lower()
    plan = QueryPlan(raw=text, rewritten=text.strip())
    if re.search(r"\bjain\b", t):
        plan.diet = "jain"
    elif re.search(r"\b(pure\s*veg|only\s*veg|vegetarian|veg only|shuddh)\b", t) or (re.search(r"\bveg\b", t) and not re.search(r"non[\s-]?veg", t)):
        plan.diet = "veg"
    elif re.search(r"non[\s-]?veg|chicken|mutton|fish|prawn|biryani", t):
        plan.diet = "non_veg" if not re.search(r"\bboth\b|\bveg and non", t) else "mixed"
    m = _GUESTS.search(t)
    if m:
        plan.guest_count = int(m.group(1))
    for word, key in _FESTIVAL_WORDS.items():
        if word in t:
            plan.festival_keys.append(key)
    if re.search(r"budget|cheap|economy|affordable|low cost", t):
        plan.price_band = "budget"
    elif re.search(r"premium|luxury|royal|grand|lavish", t):
        plan.price_band = "premium"

    if re.search(r"\b(price|prices|pricing|cost|costs|rate|rates|how much|per plate|quote|quotation|budget|rupees|expensive|charge|charges)\b|₹|\brs\.?\s?\d", t):
        plan.intent, plan.needs_live_prices = "pricing", True
    elif re.search(r"\b(add|remove|replace|swap|change|instead|make it|more guests|less guests|increase|reduce)\b", t):
        plan.intent, plan.needs_live_prices = "modification", True
    elif re.search(r"cancel|refund|advance|payment|policy|terms|deposit|gst|invoice", t):
        plan.intent, plan.source_types = "policy", ["policy", "faq"]
    elif plan.festival_keys and re.search(r"offer|discount|deal|festival", t):
        plan.intent, plan.source_types = "festival", ["festival_rules", "discount_rules"]
    elif re.search(r"menu|dish|items?|starter|dessert|counter|curry|biryani|sweet|serve|include|what do you", t):
        plan.intent, plan.source_types = "menu", ["menu_catalog", "package_template", "historical_quote"]
    elif re.search(r"book|confirm|lock|go ahead|finali[sz]e|done deal", t):
        plan.intent = "booking"
    elif re.search(r"^(hi|hello|hey|namaste|namaskaram|good (morning|evening))\b", t) and len(t) < 40:
        plan.intent, plan.needs_retrieval = "smalltalk", False
    elif re.search(r"human|manager|talk to (someone|a person)|call me", t):
        plan.intent, plan.needs_retrieval = "escalation", False
    return plan


async def plan_query(text: str, *, use_llm: bool = True) -> QueryPlan:
    plan = heuristic_plan(text)
    if not use_llm or plan.intent in ("smalltalk", "escalation"):
        return plan
    try:
        from app.agent.llm import get_llm

        llm = get_llm()
        if llm is None:
            return plan
        rewritten = await llm.complete_short(
            "Rewrite this Hyderabad catering customer message as one clear English search query for a menu/policy "
            "knowledge base. Keep dish names, diet, guest count and festival names. Reply with the query only.\n\n"
            f"Message: {text}"
        )
        if rewritten and len(rewritten) < 300:
            plan.rewritten = rewritten.strip().strip('"')
    except Exception:  # noqa: BLE001
        pass
    return plan
