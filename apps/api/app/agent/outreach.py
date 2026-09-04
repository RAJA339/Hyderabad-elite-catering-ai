"""Anvi opens the conversation, instead of waiting to be spoken to.

Someone who fills in the enquiry form has already told us the occasion, the date, the guest
count and the diet. Making them wait for a callback to hear a price wastes the one moment
they are actually thinking about their event. So the form hands those details straight to
the normal agent pipeline as if the customer had typed them, and whatever Anvi replies —
usually two or three priced menus — is delivered on whichever channel we can reach them on.

The reply is produced by the same orchestrator as every other turn, which means the same
tools, the same guardrails, and the same rule that every rupee comes from a tool call.
"""
from __future__ import annotations

from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.notify.channels import send_email

log = get_logger("outreach")


def compose_opening(*, name: str, occasion: str | None, event_date: str | None, guests: int | None,
                    diet: str | None, message: str | None) -> str:
    """The enquiry form, phrased as the message the customer would have typed. Anvi's pipeline
    reads this exactly as it reads a WhatsApp message, so discovery and pricing just work."""
    bits = [f"Hi, I'm {name.strip()}."]
    want = []
    if occasion:
        want.append(occasion.strip().lower())
    if guests:
        want.append(f"{guests} guests")
    if diet:
        want.append({"veg": "pure veg", "non_veg": "non-veg", "mixed": "veg and non-veg", "jain": "Jain"}.get(diet, diet))
    if want:
        bits.append("I'm planning catering for a " + ", ".join(want) + ".")
    if event_date:
        bits.append(f"The date is {event_date}.")
    if message and message.strip():
        bits.append(message.strip())
    bits.append("Could you send me menu options with prices?")
    return " ".join(bits)


async def greet_new_enquiry(*, tenant_id: UUID, wa_id: str, name: str, email: str | None, opening: str) -> dict:
    """Run one agent turn on the enquiry and deliver it. Best-effort: a failure here must never
    surface to the person who just submitted a form, so everything is caught and logged."""
    from app.agent.orchestrator import handle_inbound  # local: avoids a cycle at import time

    result = {"replied": False, "channels": []}
    try:
        reply = await handle_inbound(tenant_id=tenant_id, wa_id=wa_id, text=opening, profile_name=name, channel="web_chat")
    except Exception as e:  # noqa: BLE001
        log.error("outreach_agent_failed", error=f"{type(e).__name__}: {e}", wa_id=wa_id)
        return result
    result["replied"] = True
    text = reply.text

    if email:
        s = get_settings()
        body = (f"Namaste {name.split()[0] if name.strip() else 'there'},\n\n{text}\n\n"
                f"Reply to this email, or continue the conversation with me here: {s.public_web_url.rstrip('/')}/#chat\n\n"
                "— Anvi, Hyderabad Elite Catering")
        if await send_email(email, "Your catering menu and prices", body):
            result["channels"].append("email")

    # A real WhatsApp number reachable inside the 24-hour service window gets it there too;
    # outside the window Meta rejects a free-form send and only a template would deliver.
    from app.whatsapp.client import WhatsAppClient

    client = WhatsAppClient()
    if client.enabled and not wa_id.startswith("web:"):
        try:
            await client.send_text(wa_id, text)
            result["channels"].append("whatsapp")
        except Exception as e:  # noqa: BLE001
            log.info("outreach_whatsapp_skipped", reason=f"{type(e).__name__}: {e}",
                     note="outside the 24h window a template is required")

    log.info("outreach_sent", wa_id=wa_id, channels=result["channels"], chars=len(text))
    return result
