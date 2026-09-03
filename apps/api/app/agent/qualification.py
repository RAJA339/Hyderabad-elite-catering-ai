"""Lead qualification FSM + lightweight extractors (dates, guests, diet, budget, occasion).
The LLM does the conversation; this module guarantees we track what is known and cap guests."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

REQUIRED = ("event_date", "guest_count", "diet", "venue_area", "budget", "occasion")

OCCASIONS = {
    "wedding": ("wedding", "marriage", "pelli", "reception", "sangeet", "haldi", "mehendi", "engagement", "nischitartham"),
    "housewarming": ("housewarming", "gruhapravesam", "griha pravesh", "new home"),
    "birthday": ("birthday", "puttina roju", "bday"),
    "corporate": ("corporate", "office", "team lunch", "conference", "annual day", "offsite"),
    "naming_ceremony": ("naming", "barasala", "cradle", "namakaranam"),
    "half_saree": ("half saree", "langa voni", "voni"),
    "anniversary": ("anniversary",),
    "festival_party": ("diwali party", "sankranti", "ugadi", "iftar", "christmas", "new year"),
    "pooja": ("pooja", "puja", "satyanarayana", "vratham", "homam"),
    "funeral": ("funeral", "dashadina", "karma", "dinam"),
}
AREAS = ("kompally", "gachibowli", "madhapur", "hitech city", "kukatpally", "miyapur", "banjara hills", "jubilee hills",
         "secunderabad", "begumpet", "ameerpet", "dilsukhnagar", "lb nagar", "uppal", "kondapur", "manikonda", "nizampet",
         "bachupally", "tolichowki", "mehdipatnam", "attapur", "shamshabad", "hayathnagar", "medchal", "alwal", "sainikpuri",
         "ecil", "malkajgiri", "tarnaka", "himayatnagar", "abids", "koti", "charminar", "old city", "narsingi", "kokapet",
         "financial district", "nanakramguda", "chandanagar", "lingampally", "patancheru")
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


@dataclass
class Qualification:
    fields: dict = field(default_factory=dict)
    turns: int = 0
    over_limit: bool = False

    @property
    def missing(self) -> list[str]:
        return [f for f in REQUIRED if f not in self.fields]

    @property
    def is_qualified(self) -> bool:
        return not self.missing and not self.over_limit

    def to_dict(self) -> dict:
        return {"fields": self.fields, "missing": self.missing, "turns": self.turns, "over_limit": self.over_limit, "qualified": self.is_qualified}

    @classmethod
    def from_dict(cls, d: dict | None) -> Qualification:
        d = d or {}
        return cls(fields=dict(d.get("fields", {})), turns=int(d.get("turns", 0)), over_limit=bool(d.get("over_limit", False)))


def parse_date(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    t = text.lower()
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3,9})(?:\s*(\d{4}))?\b", t)
    if m and m.group(2)[:3] in MONTHS:
        d, mo = int(m.group(1)), MONTHS[m.group(2)[:3]]
        y = int(m.group(3)) if m.group(3) else today.year
        try:
            cand = date(y, mo, d)
            if cand < today and not m.group(3):
                cand = date(y + 1, mo, d)
            return cand
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        y = y + 2000 if y < 100 else y
        try:
            cand = date(y, mo, d)
            if cand < today and not m.group(3):
                cand = date(y + 1, mo, d)
            return cand
        except ValueError:
            return None
    m = re.search(r"\b(?:in|after)\s+(\d{1,2})\s+(day|week|month)s?\b", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return today + timedelta(days=n * {"day": 1, "week": 7, "month": 30}[unit])
    if "tomorrow" in t:
        return today + timedelta(days=1)
    if "next month" in t:
        return (today.replace(day=1) + timedelta(days=32)).replace(day=15)
    return None


def parse_guests(text: str) -> int | None:
    m = re.search(r"(\d{2,4})\s*(?:\+\s*)?(?:guests?|people|pax|members|persons|heads|plates?|mandi|janalu|ppl)", text, re.I)
    if not m:
        m = re.search(r"(?:around|approx|about|for)\s+(\d{2,4})\b", text, re.I)
    return int(m.group(1)) if m else None


def parse_diet(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bjain\b", t):
        return "jain"
    if re.search(r"\bboth\b|veg\s*(and|&|\+)\s*non|mixed|non[\s-]?veg\s*(and|&|\+)\s*veg", t):
        return "mixed"
    if re.search(r"non[\s-]?veg|chicken|mutton|fish|prawn|biryani|egg", t):
        return "non_veg"
    if re.search(r"\b(pure\s*veg|all\s*veg|only\s*veg|veg\s*only|vegetarian|veg)\b", t):
        return "veg"
    return None


def parse_budget(text: str) -> tuple[int, int] | None:
    t = text.lower().replace(",", "")
    m = re.search(r"(\d{3,4})\s*(?:-|to|–)\s*(\d{3,4})\s*(?:per\s*(?:plate|head|person)|/plate|pp)?", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?:budget|around|about|max|upto|up to)\s*(?:rs\.?|₹)?\s*(\d{3,4})\s*(?:per\s*(?:plate|head|person)|/plate|pp)", t)
    if m:
        v = int(m.group(1))
        return int(v * 0.85), v
    m = re.search(r"(?:rs\.?|₹)\s*(\d{3,4})\s*(?:per\s*(?:plate|head|person)|/plate|pp)?", t)
    if m:
        v = int(m.group(1))
        return int(v * 0.85), int(v * 1.15)
    return None


def parse_occasion(text: str) -> str | None:
    t = text.lower()
    for key, words in OCCASIONS.items():
        if any(w in t for w in words):
            return key
    return None


def parse_area(text: str) -> str | None:
    t = text.lower()
    for a in AREAS:
        if a in t:
            return a.title()
    return None


def extract(text: str, q: Qualification, *, max_guests: int = 500, today: date | None = None) -> Qualification:
    """Merge whatever the message reveals into the qualification state (never overwrites with None)."""
    q.turns += 1
    if (d := parse_date(text, today)) and "event_date" not in q.fields:
        q.fields["event_date"] = d.isoformat()
    if (g := parse_guests(text)) is not None:
        if g > max_guests:
            q.over_limit = True
            q.fields["requested_guest_count"] = g
        else:
            q.over_limit = False
            q.fields["guest_count"] = g
    if (diet := parse_diet(text)):
        q.fields["diet"] = diet
    if (b := parse_budget(text)):
        q.fields["budget"] = {"min_per_plate": b[0], "max_per_plate": b[1]}
    if (o := parse_occasion(text)):
        q.fields["occasion"] = o
    if (a := parse_area(text)):
        q.fields["venue_area"] = a
    return q


NEXT_QUESTION = {
    "event_date": "which date is the event",
    "guest_count": "roughly how many guests (we serve up to 500)",
    "diet": "veg, non-veg, or a mix (or Jain)",
    "venue_area": "which area is the venue in",
    "budget": "what budget per plate feels right",
    "occasion": "what's the occasion",
}


def next_questions(q: Qualification, limit: int = 2) -> list[str]:
    return [NEXT_QUESTION[f] for f in q.missing[:limit]]
