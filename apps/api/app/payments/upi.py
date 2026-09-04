"""UPI collection with nothing to approve.

Razorpay needs KYC and a settlement account; the WhatsApp API needs Meta. A UPI intent link
needs neither: `upi://pay?pa=<vpa>&am=<amount>` opens PhonePe, GPay, Paytm or any UPI app
with the payee and the exact amount filled in, and the same string as a QR does it from a
laptop screen. The customer pays, types the 12-digit UTR from their app, the owner gets an
alert and confirms with one tap. Money goes straight to the owner's account.

The VPA is the address behind the owner's PhonePe/GPay number; the number alone is shown as
a fallback for people who prefer to type it in.
"""
from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import quote

from app.core.config import get_settings

UTR_RE = re.compile(r"^\d{12}$")


def configured() -> bool:
    s = get_settings()
    return bool(s.upi_vpa or s.upi_payee_phone)


def payee_phone_display() -> str | None:
    s = get_settings()
    digits = "".join(ch for ch in (s.upi_payee_phone or "") if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91 {digits[2:7]} {digits[7:]}"
    return f"+{digits}" if digits else None


def upi_link(amount: Decimal | int | str, *, note: str, ref: str) -> str | None:
    """Intent URL understood by every UPI app. `tr` carries the quote number so the payment
    is recognisable in the owner's app; `tn` is the note the customer sees."""
    s = get_settings()
    if not s.upi_vpa:
        return None
    amt = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"
    q = {"pa": s.upi_vpa, "pn": s.upi_payee_name, "am": amt, "cu": "INR", "tn": note[:50], "tr": ref[:35]}
    return "upi://pay?" + "&".join(f"{k}={quote(str(v), safe='')}" for k, v in q.items())


def qr_svg(payload: str) -> str:
    """Scalable QR of the intent string. Sized by CSS, not by the fixed mm the library emits."""
    import qrcode
    import qrcode.image.svg as svg

    img = qrcode.make(payload, image_factory=svg.SvgPathImage, box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    out = img.to_string(encoding="unicode")
    out = re.sub(r'\swidth="[^"]*"', ' width="100%"', out, count=1)
    out = re.sub(r'\sheight="[^"]*"', ' height="100%"', out, count=1)
    # the library paints black on nothing; give the modules a colour the page can override
    return out.replace("<path ", '<path fill="currentColor" ', 1)


def payment_card(*, amount: Decimal | int | str, quote_number: str, payment_id: str, portal_token: str | None) -> dict | None:
    """Everything a client needs to render a pay-by-UPI card, or None when UPI is not set up."""
    if not configured():
        return None
    s = get_settings()
    link = upi_link(amount, note=f"Advance {quote_number} HEC", ref=quote_number)
    return {
        "type": "upi",
        "amount": str(Decimal(str(amount)).quantize(Decimal("1"))),
        "quote_number": quote_number,
        "payment_id": payment_id,
        "payee": s.upi_payee_name,
        "vpa": s.upi_vpa,
        "phone": payee_phone_display(),
        "link": link,
        "qr_svg": qr_svg(link) if link else None,
        "claim_url": f"/api/portal/{portal_token}/upi-claim" if portal_token else None,
        "apps": ["PhonePe", "Google Pay", "Paytm", "BHIM"],
    }


def valid_utr(utr: str) -> str | None:
    digits = "".join(ch for ch in utr if ch.isdigit())
    return digits if UTR_RE.match(digits) else None
