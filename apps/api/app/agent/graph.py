"""The shape of a catering sale, as an explicit state machine.

A single prompt asking a model to "qualify, then price, then close" leaves the order to
chance: it will price before it understands the event, discount before it has been pushed,
or keep asking questions after the customer is ready to pay. This module makes the stage
explicit and derives it from facts already in the database, so every turn knows where it is.

    DISCOVER  → learn the event and, crucially, the motive behind it
    DESIGN    → propose priced packages built around that motive
    NEGOTIATE → modify, justify against the market, offer only when pushed
    CLOSE     → lock the price, take the advance
    WON       → confirmed; stop selling

Each phase carries its own goal, the tools that make sense in it, and the one thing that
moves the conversation forward. That is the whole value of a graph here — a phase, a policy
per phase, and a deterministic transition — so it is written directly against our own state
rather than adding a framework to hold four nodes.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tool names, kept as strings so this module stays independent of the tool belt.
ALL_TOOLS = ("save_lead_field", "price_package", "modify_quote", "festival_offers", "market_snapshot",
             "lock_price", "record_advance", "suggest_upsell", "escalate_to_human")


@dataclass(frozen=True)
class Phase:
    key: str
    goal: str
    tools: tuple[str, ...]
    directive: str


DISCOVER = Phase(
    key="discover",
    goal="Understand the event and why it matters before quoting anything.",
    tools=("save_lead_field", "escalate_to_human"),
    directive=(
        "Do not price yet. Ask at most two things per message, and make one of them about the OCCASION ITSELF, "
        "not the logistics: who is coming, what the day means to them, what they want guests to remember. "
        "A housewarming for the wife's parents, a wedding reception where the groom's side is from Vijayawada, "
        "a corporate lunch that has to impress a visiting client — each of those changes the menu. "
        "Record what you learn with save_lead_field, including the motive. Move on as soon as you have date, "
        "guest count, diet and area; the rest can come while you price."
    ),
)

DESIGN = Phase(
    key="design",
    goal="Put three complete, priced menus in front of them, shaped by the motive.",
    tools=("price_package", "modify_quote", "market_snapshot", "save_lead_field", "suggest_upsell", "escalate_to_human"),
    directive=(
        "Call price_package now and present the packages in its `present_in_order`, following its `talk_track`. "
        "Tie the recommendation to what you learned in discovery, in one line — 'since it's your parents' first "
        "visit, I've kept the Signature's sweets section traditional'. Name the dishes; a price without a menu is "
        "a number, not an offer."
    ),
)

NEGOTIATE = Phase(
    key="negotiate",
    goal="Answer the real objection. Change the menu before you change the price.",
    tools=("modify_quote", "market_snapshot", "festival_offers", "suggest_upsell", "price_package", "save_lead_field", "escalate_to_human"),
    directive=(
        "When they hesitate on price, your first move is market_snapshot — show what the ingredients cost this "
        "morning and what the market charges. Your second is to reshape the menu to their number with modify_quote. "
        "Only after those, check festival_offers. Never volunteer a discount that was not asked for, and never "
        "invent one: if the tool returns no offer, hold the price and sell the value."
    ),
)

CLOSE = Phase(
    key="close",
    goal="Lock the price and take the advance.",
    tools=("lock_price", "record_advance", "modify_quote", "market_snapshot", "escalate_to_human"),
    directive=(
        "They are ready. Propose locking the price for the event date, then ask for the advance and explain the "
        "cancellation policy in one line. Stop selling; make the next step obvious and easy."
    ),
)

WON = Phase(
    key="won",
    goal="Confirm, reassure, and hand over cleanly.",
    tools=("modify_quote", "escalate_to_human"),
    directive=(
        "The advance is paid. Confirm what happens next and when the team will call about final counts. "
        "Do not upsell unless they ask. If they want changes, use modify_quote and say what it does to the total."
    ),
)

PHASES = {p.key: p for p in (DISCOVER, DESIGN, NEGOTIATE, CLOSE, WON)}

_BUYING_SIGNALS = ("book", "confirm", "go ahead", "finalize", "finalise", "lock", "advance", "pay", "deposit",
                   "ok done", "let's do", "lets do", "sare", "chesukundam", "kavali")
_PRICE_PUSH = ("expensive", "costly", "high", "budget", "less", "discount", "offer", "reduce", "cheap",
               "too much", "ekkuva", "thakkuva", "adjust")


def classify(*, lead: dict, quote: dict | None, text: str, qualified: bool) -> Phase:
    """Where this conversation is. Facts first, the customer's words only to break ties."""
    stage = (lead.get("stage") or "").lower()
    low = (text or "").lower()

    if stage in ("advance_paid", "confirmed", "completed"):
        return WON
    if quote and (quote.get("status") or "") in ("locked", "accepted"):
        return CLOSE
    if any(s in low for s in _BUYING_SIGNALS) and quote:
        return CLOSE
    if quote and (stage == "negotiating" or any(s in low for s in _PRICE_PUSH)):
        return NEGOTIATE
    if quote:
        return NEGOTIATE if any(s in low for s in _PRICE_PUSH) else DESIGN
    if qualified:
        return DESIGN
    return DISCOVER


def tools_for(phase: Phase, all_tools: list[dict]) -> list[dict]:
    """The tool belt narrowed to this phase. A model that cannot reach lock_price during
    discovery cannot close before it understands the event."""
    allowed = set(phase.tools)
    return [t for t in all_tools if t.get("name") in allowed]


def directive_for(phase: Phase, *, motive: str | None) -> str:
    lines = [f"## This conversation is in the {phase.key.upper()} phase", phase.goal, "", phase.directive]
    if motive and phase.key != "discover":
        lines += ["", f"What this event is really about, in their words: “{motive}”. Every menu suggestion and every "
                      "line of reassurance should serve that."]
    return "\n".join(lines)
