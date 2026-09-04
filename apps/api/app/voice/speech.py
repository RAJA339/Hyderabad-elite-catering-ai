"""Turning a message written for a screen into something a person can hear.

Text that reads well on WhatsApp is unlistenable on a phone call. "₹1,25,000" is silent to
a speech engine, a bulleted list of three packages becomes a wall of sound with no pause to
answer into, and a URL read aloud is meaningless. This module rewrites a reply for the ear:
rupees spoken the Indian way, one idea per sentence, at most a few sentences, and a single
question at the end so the caller knows it is their turn.

Nothing here changes what Anvi decided to say — the numbers, menus and offers are already
fixed by the tools. This only changes how it sounds.
"""
from __future__ import annotations

import re

MAX_SENTENCES = 6
_URL = re.compile(r"https?://\S+")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
_BULLET = re.compile(r"^\s*[•\-*]\s*", re.M)
_RUPEE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")


def say_amount(n: int) -> str:
    """125000 → 'one lakh twenty five thousand rupees'. Indian units, because a caller in
    Hyderabad thinks in lakhs, not in hundreds of thousands."""
    if n < 0:
        return f"minus {say_amount(-n)}"
    if n >= 10_000_000:
        cr, rest = divmod(n, 10_000_000)
        return f"{_words(cr)} crore" + (f" {say_amount(rest)}" if rest else " rupees")
    if n >= 100_000:
        lakh, rest = divmod(n, 100_000)
        return f"{_words(lakh)} lakh" + (f" {say_amount(rest)}" if rest else " rupees")
    if n >= 1_000:
        th, rest = divmod(n, 1_000)
        return f"{_words(th)} thousand" + (f" {say_amount(rest)}" if rest else " rupees")
    return f"{_words(n)} rupees"


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (f" {_ONES[o]}" if o else "")
    h, rest = divmod(n, 100)
    return f"{_ONES[h]} hundred" + (f" {_words(rest)}" if rest else "")


def for_speech(text: str, *, max_sentences: int = MAX_SENTENCES) -> str:
    """The whole rewrite: strip what cannot be heard, speak the money, keep it short."""
    # A link cannot be heard, and neither can the label introducing it ("View it here:"),
    # so the whole clause goes rather than leaving a sentence hanging on a colon.
    t = re.sub(r"[^.!?\n]*?:\s*" + _URL.pattern, "", text)
    t = _URL.sub("", t)
    t = _EMOJI.sub("", t)
    t = _BULLET.sub("", t)
    t = t.replace("*", "").replace("_", " ").replace("#", " ")
    # "per plate" before the money, so the slash is gone by the time digits become words.
    t = re.sub(r"\s*/\s*(plate|head|person|pax)\b", r" per \1", t, flags=re.I)
    t = _RUPEE.sub(lambda m: say_amount(int(float(m.group(1).replace(",", "")))), t)
    t = t.replace("—", ",").replace("–", ",")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" ,", ",", t)
    t = re.sub(r"\n{2,}", "\n", t).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", t) if s.strip()]
    if len(sentences) > max_sentences:
        # Keep the opening and whatever question ends it: the caller needs a prompt to answer.
        question = next((s for s in reversed(sentences) if s.rstrip().endswith("?")), None)
        kept = sentences[: max_sentences - 1]
        if question and question not in kept:
            kept.append(question)
        sentences = kept
    out = " ".join(sentences)
    return out or "Sorry, could you say that again?"


def ssml(text: str, *, voice_lang: str = "en-IN") -> str:
    """Light SSML: a short pause between sentences so it does not sound rushed."""
    body = "".join(f"{s.strip()}<break time=\"350ms\"/>" for s in re.split(r"(?<=[.!?])\s+", text) if s.strip())
    return f'<speak xml:lang="{voice_lang}">{body}</speak>'
