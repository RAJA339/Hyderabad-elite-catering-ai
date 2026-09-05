"""What goes into one catering plate of each dish, in the ingredient keys the market feed prices.

The pricing engine never sees a menu price. It sees a recipe, today's wholesale rate for each
line, the labour a dish takes per guest, and works upward from there. So the owner's menu is
expressed here as raw quantities per guest (kg, l, pc, dozen) at buffet portions, not
restaurant ones. Labour is rupees per guest for that dish alone: a staple that comes off one
big vessel is cheap, a biryani on dum or a fried starter done in batches is not.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal as D


@dataclass(frozen=True)
class Recipe:
    lines: dict[str, D]        # ingredient key → qty per guest in the ingredient's unit
    labour: D                  # ₹ per guest
    jain: bool = False         # no onion, garlic or root vegetables in the recipe
    setup: D = D("0")          # fixed ₹ per event (live counters only)


def _r(labour: float, jain: bool = False, setup: float = 0, **lines: float) -> Recipe:
    return Recipe({k: D(str(v)) for k, v in lines.items()}, D(str(labour)), jain, D(str(setup)))


# Ingredients the demo catalogue did not need; the loader adds them with an opening wholesale
# rate so costing works from the first boot, and the market feed updates them afterwards.
EXTRA_INGREDIENTS: dict[str, tuple[str, str, str, float, bool]] = {
    # key: (name, unit, category, opening ₹/unit wholesale, volatile)
    "gongura": ("Gongura (sorrel leaves)", "kg", "vegetable", 40, True),
    "dondakaya": ("Dondakaya (ivy gourd)", "kg", "vegetable", 40, True),
    "bendakaya": ("Bendakaya (okra)", "kg", "vegetable", 45, True),
    "cauliflower": ("Cauliflower", "kg", "vegetable", 35, True),
    "chana": ("Kabuli chana", "kg", "grain", 95, False),
    "chana_dal": ("Chana dal", "kg", "grain", 92, False),
    "rava": ("Rava (semolina)", "kg", "grain", 48, False),
    "jaggery": ("Jaggery", "kg", "other", 62, False),
    "ice_cream": ("Ice cream (bulk tub)", "l", "dairy", 150, False),
    "paan": ("Meetha paan (made up)", "pc", "other", 5, False),
    "disposables": ("Disposable plate set, tissue, bin cover", "pc", "other", 4.5, False),
    "water_bottle": ("Packaged water 500 ml", "pc", "other", 7, False),
}

RECIPES: dict[str, Recipe] = {
    # ── rice & breads ──
    "veg_biryani": _r(3, rice=0.065, mixed_veg=0.035, onion=0.02, curd=0.01, oil=0.01, ghee=0.002, spices=0.004, coriander_mint=0.004, ginger_garlic=0.002),
    "bagara_rice": _r(2, rice=0.065, onion=0.015, oil=0.008, ghee=0.003, spices=0.003, coriander_mint=0.003),
    "white_rice": _r(0.6, True, sona_rice=0.07),
    "pulihora": _r(1.2, True, sona_rice=0.035, tamarind=0.004, oil=0.005, spices=0.003, dry_fruits=0.001),
    "puri": _r(1.8, True, wheat_flour=0.03, oil=0.01),
    "chapati": _r(1.8, True, wheat_flour=0.035, oil=0.003),
    "phulka": _r(1.5, True, wheat_flour=0.025, ghee=0.002),
    # ── curries & gravies (veg) ──
    "sambar": _r(0.9, toor_dal=0.012, mixed_veg=0.025, tamarind=0.003, onion=0.006, tomato=0.008, spices=0.002, oil=0.003),
    "rasam": _r(0.6, True, toor_dal=0.005, tomato=0.012, tamarind=0.003, spices=0.002, oil=0.002, coriander_mint=0.001),
    "dal_tadka": _r(0.9, toor_dal=0.018, tomato=0.01, onion=0.006, ghee=0.002, spices=0.002),
    "majjiga_charu": _r(0.8, True, curd=0.035, chana_dal=0.004, coconut=0.015, spices=0.002, oil=0.002),
    "gutti_vankaya": _r(2, brinjal=0.05, onion=0.015, tamarind=0.003, spices=0.004, oil=0.008, dry_fruits=0.002, coconut=0.015),
    "alu_masala": _r(1.5, potato=0.055, onion=0.015, tomato=0.012, oil=0.007, spices=0.003),
    "alu_tomato_curry": _r(1.5, potato=0.05, tomato=0.03, onion=0.012, oil=0.007, spices=0.003),
    "paneer_butter_masala": _r(2, paneer=0.03, tomato=0.03, onion=0.012, butter=0.004, cream=0.005, dry_fruits=0.002, spices=0.002, oil=0.004),
    "chole_masala": _r(1.5, chana=0.025, onion=0.018, tomato=0.018, oil=0.007, spices=0.003, ginger_garlic=0.002),
    "dondakaya_fry": _r(1.5, True, dondakaya=0.045, oil=0.008, spices=0.003),
    "bendakaya_fry": _r(1.5, True, bendakaya=0.045, oil=0.008, spices=0.003),
    # ── chutneys & sides ──
    "gongura_chutney": _r(0.7, gongura=0.018, green_chilli=0.003, oil=0.004, spices=0.001, onion=0.004),
    "vankaya_dosakaya_chutney": _r(0.7, brinjal=0.012, mixed_veg=0.012, tamarind=0.002, green_chilli=0.002, oil=0.003, spices=0.001),
    "papad": _r(0.3, True, wheat_flour=0.006, oil=0.003),
    "curd": _r(0.2, True, curd=0.04),
    "raita": _r(0.4, curd=0.025, onion=0.008, tomato=0.006, spices=0.001),
    "salad": _r(0.6, onion=0.02, tomato=0.02, lemon=0.004, green_chilli=0.002),
    "karapodi_ghee": _r(0.3, True, toor_dal=0.004, spices=0.003, ghee=0.003),
    "meetha_paan": _r(0.1, True, paan=1.0),
    # ── starters ──
    "mirchi_bajji": _r(1.5, True, green_chilli=0.02, wheat_flour=0.012, oil=0.01, tamarind=0.002, spices=0.001),
    "vada": _r(1.5, True, urad_dal=0.02, oil=0.01, green_chilli=0.002, spices=0.001),
    "masala_vada": _r(1.5, chana_dal=0.02, onion=0.008, oil=0.01, green_chilli=0.002, spices=0.001),
    "alu_65": _r(1.5, potato=0.04, wheat_flour=0.006, oil=0.01, spices=0.003, ginger_garlic=0.002),
    "cauliflower_65": _r(1.5, cauliflower=0.04, wheat_flour=0.006, oil=0.01, spices=0.003, ginger_garlic=0.002),
    "chicken_fry": _r(2.5, chicken=0.055, oil=0.01, spices=0.004, ginger_garlic=0.003, curd=0.005),
    "fish_fry": _r(2.5, fish=0.05, oil=0.01, spices=0.004, ginger_garlic=0.002, lemon=0.002),
    "prawns_fry": _r(2.5, prawns=0.04, oil=0.008, spices=0.004, ginger_garlic=0.002),
    # ── non-veg mains ──
    "chicken_biryani": _r(4.5, chicken=0.11, rice=0.075, onion=0.025, curd=0.01, oil=0.012, ghee=0.003, spices=0.006, coriander_mint=0.005, ginger_garlic=0.004),
    "mutton_biryani": _r(5, mutton=0.09, rice=0.075, onion=0.025, curd=0.01, oil=0.012, ghee=0.004, spices=0.006, coriander_mint=0.005, ginger_garlic=0.004),
    "chicken_curry": _r(2.2, chicken=0.08, onion=0.02, tomato=0.015, oil=0.008, spices=0.004, ginger_garlic=0.003),
    "mutton_curry": _r(2.5, mutton=0.065, onion=0.02, tomato=0.015, oil=0.008, spices=0.004, ginger_garlic=0.003),
    "prawns_curry": _r(2.5, prawns=0.05, onion=0.02, tomato=0.012, coconut=0.015, oil=0.007, spices=0.004),
    # ── sweets ──
    "purnalu": _r(1.4, True, chana_dal=0.014, jaggery=0.014, wheat_flour=0.006, urad_dal=0.004, oil=0.008, coconut=0.006),
    "bobbatlu": _r(1.5, True, chana_dal=0.014, jaggery=0.014, wheat_flour=0.014, ghee=0.004),
    "double_ka_meetha": _r(1.2, True, bread=0.022, milk=0.035, sugar=0.015, ghee=0.004, dry_fruits=0.002),
    "gulab_jamun": _r(0.9, True, milk=0.03, sugar=0.02, wheat_flour=0.006, oil=0.004),
    "rava_kesari": _r(0.9, True, rava=0.018, sugar=0.018, ghee=0.005, dry_fruits=0.002),
    "chakkara_pongali": _r(0.9, True, sona_rice=0.018, jaggery=0.018, milk=0.02, ghee=0.005, dry_fruits=0.002),
    "vanilla_ice_cream": _r(0.4, True, ice_cream=0.05),
    "butterscotch_ice_cream": _r(0.4, True, ice_cream=0.05),
    "fruit_salad": _r(0.8, True, fruits=0.06, sugar=0.004),
    # ── service ──
    "disposables": _r(0, True, disposables=1.0),
    "water": _r(0, True, water_bottle=1.0),
}

ROOT_VEG = {"potato", "onion", "ginger_garlic", "raw_banana", "cauliflower"}
DAIRY = {"milk", "curd", "ghee", "butter", "cream", "paneer", "ice_cream"}
MEAT = {"chicken", "mutton", "fish", "prawns"}


def contains_for(recipe: Recipe) -> list[str]:
    keys = set(recipe.lines)
    out: list[str] = []
    if "onion" in keys:
        out.append("onion")
    if "ginger_garlic" in keys:
        out.append("garlic")
    if "potato" in keys:
        out.append("potato")
    if keys & DAIRY:
        out.append("dairy")
    if "dry_fruits" in keys:
        out.append("nuts")
    if "egg" in keys:
        out.append("egg")
    if keys & MEAT:
        out.append("meat")
    return out


def jain_ok(recipe: Recipe) -> bool:
    return recipe.jain and not (set(recipe.lines) & (ROOT_VEG | MEAT | {"egg"}))
