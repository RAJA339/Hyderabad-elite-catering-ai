"""Indian + Hyderabad festival calendar (2026–2027). Dates follow the official Telangana
holiday list / Panchangam; verify yearly. demand_multiplier > 1 marks peak demand windows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Festival:
    key: str
    name: str
    starts_on: date
    ends_on: date
    demand_multiplier: float = 1.0
    tags: tuple[str, ...] = ()
    region: str = "Hyderabad"


FESTIVALS: list[Festival] = [
    Festival("sankranti_2026", "Sankranti / Pongal", date(2026, 1, 13), date(2026, 1, 16), 1.25, ("veg_heavy", "sweets", "family")),
    Festival("republic_day_2026", "Republic Day", date(2026, 1, 26), date(2026, 1, 26), 1.05, ("corporate",)),
    Festival("maha_shivaratri_2026", "Maha Shivaratri", date(2026, 2, 15), date(2026, 2, 15), 1.05, ("veg_heavy", "fasting")),
    Festival("ramzan_2026", "Ramzan / Eid-ul-Fitr", date(2026, 2, 18), date(2026, 3, 20), 1.30, ("non_veg", "haleem", "iftar", "hyderabadi")),
    Festival("holi_2026", "Holi", date(2026, 3, 3), date(2026, 3, 4), 1.10, ("sweets", "chaat")),
    Festival("ugadi_2026", "Ugadi", date(2026, 3, 19), date(2026, 3, 19), 1.30, ("veg_heavy", "telugu_new_year", "pachadi")),
    Festival("sri_rama_navami_2026", "Sri Rama Navami", date(2026, 3, 27), date(2026, 3, 27), 1.10, ("veg_heavy", "panakam")),
    Festival("wedding_season_summer_2026", "Wedding Season (Summer)", date(2026, 4, 15), date(2026, 6, 15), 1.40, ("wedding", "peak")),
    Festival("bakrid_2026", "Bakrid / Eid-ul-Adha", date(2026, 5, 27), date(2026, 5, 28), 1.25, ("non_veg", "mutton", "hyderabadi")),
    Festival("bonalu_2026", "Bonalu", date(2026, 7, 12), date(2026, 8, 2), 1.15, ("hyderabadi", "telangana", "veg_heavy")),
    Festival("independence_day_2026", "Independence Day", date(2026, 8, 15), date(2026, 8, 15), 1.05, ("corporate",)),
    Festival("raksha_bandhan_2026", "Raksha Bandhan", date(2026, 8, 28), date(2026, 8, 28), 1.05, ("sweets", "family")),
    Festival("krishna_janmashtami_2026", "Krishna Janmashtami", date(2026, 9, 4), date(2026, 9, 4), 1.05, ("veg_heavy", "sweets")),
    Festival("ganesh_chaturthi_2026", "Ganesh Chaturthi (Vinayaka Chavithi)", date(2026, 9, 14), date(2026, 9, 24), 1.35, ("veg_heavy", "sweets", "community", "hyderabadi")),
    Festival("bathukamma_2026", "Bathukamma", date(2026, 10, 9), date(2026, 10, 17), 1.30, ("telangana", "veg_heavy", "women", "hyderabadi")),
    Festival("dasara_2026", "Dasara / Vijayadashami", date(2026, 10, 11), date(2026, 10, 20), 1.35, ("family", "sweets", "non_veg_after")),
    Festival("diwali_2026", "Diwali / Deepavali", date(2026, 11, 6), date(2026, 11, 10), 1.40, ("sweets", "corporate", "family", "peak")),
    Festival("wedding_season_winter_2026", "Wedding Season (Winter)", date(2026, 11, 15), date(2027, 2, 28), 1.45, ("wedding", "peak")),
    Festival("christmas_2026", "Christmas", date(2026, 12, 24), date(2026, 12, 26), 1.20, ("corporate", "cake", "non_veg")),
    Festival("new_year_2027", "New Year's Eve", date(2026, 12, 30), date(2027, 1, 1), 1.35, ("corporate", "party", "peak", "live_counters")),
    Festival("sankranti_2027", "Sankranti / Pongal", date(2027, 1, 13), date(2027, 1, 16), 1.25, ("veg_heavy", "sweets", "family")),
    Festival("ramzan_2027", "Ramzan / Eid-ul-Fitr", date(2027, 2, 8), date(2027, 3, 10), 1.30, ("non_veg", "haleem", "iftar", "hyderabadi")),
    Festival("ugadi_2027", "Ugadi", date(2027, 4, 7), date(2027, 4, 7), 1.30, ("veg_heavy", "telugu_new_year")),
]


def festivals_around(d: date, before_days: int = 21, after_days: int = 3) -> list[Festival]:
    """Festivals whose window is within [d - after_days, d + before_days] — i.e. upcoming
    festivals the event might be for, plus a festival that just started."""
    out = []
    for f in FESTIVALS:
        if f.starts_on <= d <= f.ends_on:
            out.append(f)
        elif 0 < (f.starts_on - d).days <= before_days:
            out.append(f)
        elif 0 < (d - f.ends_on).days <= after_days:
            out.append(f)
    return sorted(out, key=lambda f: f.starts_on)


def demand_multiplier_for(d: date) -> float:
    m = 1.0
    for f in FESTIVALS:
        if f.starts_on <= d <= f.ends_on:
            m = max(m, f.demand_multiplier)
    return m
