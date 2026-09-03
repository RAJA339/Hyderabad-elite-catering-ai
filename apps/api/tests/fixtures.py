from decimal import Decimal as D

from app.pricing.models import IngredientPrice, MenuItem, RecipeLine
from app.pricing.packages import PackageTemplate

PRICES = {
    "chicken": IngredientPrice("chicken", "Chicken", "kg", D("230"), D("290"), D("14"), True),
    "mutton": IngredientPrice("mutton", "Mutton", "kg", D("780"), D("900"), D("2"), True),
    "paneer": IngredientPrice("paneer", "Paneer", "kg", D("360"), D("420"), D("1")),
    "onion": IngredientPrice("onion", "Onion", "kg", D("32"), D("45"), D("20"), True),
    "tomato": IngredientPrice("tomato", "Tomato", "kg", D("28"), D("40"), D("-5"), True),
    "rice": IngredientPrice("rice", "Basmati", "kg", D("95"), D("120"), D("0")),
    "oil": IngredientPrice("oil", "Oil", "l", D("130"), D("150"), D("0")),
    "spices": IngredientPrice("spices", "Spices", "kg", D("600"), D("800"), D("0")),
    "milk": IngredientPrice("milk", "Milk", "l", D("56"), D("64"), D("0")),
    "sugar": IngredientPrice("sugar", "Sugar", "kg", D("44"), D("50"), D("0")),
    "raw_banana": IngredientPrice("raw_banana", "Raw banana", "kg", D("40"), D("55"), D("0")),
    "potato": IngredientPrice("potato", "Potato", "kg", D("26"), D("35"), D("0")),
}


def item(slug, name, cat, diet, recipe, **kw):
    return MenuItem(slug=slug, name=name, category_key=cat, diet=diet, recipe=tuple(RecipeLine(k, D(str(q))) for k, q in recipe), **kw)


CATALOG = {m.slug: m for m in [
    item("chicken_biryani", "Chicken Dum Biryani", "main_nonveg", "non_veg", [("chicken", 0.18), ("rice", 0.12), ("onion", 0.05), ("oil", 0.02), ("spices", 0.01)],
         labour_cost_per_guest=D("12"), contains=("onion", "garlic", "meat"), popularity=100),
    item("mutton_biryani", "Mutton Biryani", "main_nonveg", "non_veg", [("mutton", 0.16), ("rice", 0.12), ("onion", 0.05), ("oil", 0.02), ("spices", 0.01)],
         labour_cost_per_guest=D("14"), contains=("onion", "garlic", "meat"), tags=("mutton",), popularity=80),
    item("paneer_butter_masala", "Paneer Butter Masala", "main_veg", "veg", [("paneer", 0.07), ("tomato", 0.06), ("onion", 0.03), ("oil", 0.015), ("spices", 0.005)],
         labour_cost_per_guest=D("8"), contains=("onion", "garlic", "dairy"), popularity=90),
    item("aloo_curry", "Aloo Kurma", "main_veg", "veg", [("potato", 0.09), ("onion", 0.03), ("oil", 0.01), ("spices", 0.005)], labour_cost_per_guest=D("5"), contains=("onion", "potato")),
    item("raw_banana_fry", "Aratikaya Vepudu", "main_veg", "veg", [("raw_banana", 0.08), ("oil", 0.012), ("spices", 0.004)], labour_cost_per_guest=D("5"), is_jain_ok=True, popularity=40),
    item("pulihora", "Pulihora", "rice_breads", "veg", [("rice", 0.09), ("oil", 0.01), ("spices", 0.005)], labour_cost_per_guest=D("4"), is_jain_ok=True, popularity=70),
    item("gulab_jamun", "Gulab Jamun", "desserts", "veg", [("milk", 0.05), ("sugar", 0.03), ("oil", 0.005)], labour_cost_per_guest=D("3"), is_jain_ok=True, popularity=95),
    item("live_dosa", "Live Dosa Counter", "live_counters", "veg", [("rice", 0.06), ("oil", 0.01), ("potato", 0.03)], labour_cost_per_guest=D("6"),
         fixed_setup_cost=D("2500"), is_live_counter=True, contains=("potato",), popularity=85),
]}

TEMPLATES = [
    PackageTemplate("classic_veg", "classic", "veg", ("paneer_butter_masala", "aloo_curry", "pulihora", "gulab_jamun")),
    PackageTemplate("signature_veg", "signature", "veg", ("paneer_butter_masala", "aloo_curry", "pulihora", "gulab_jamun", "live_dosa")),
    PackageTemplate("royal_veg", "royal", "veg", ("paneer_butter_masala", "aloo_curry", "raw_banana_fry", "pulihora", "gulab_jamun", "live_dosa")),
    PackageTemplate("classic_nonveg", "classic", "non_veg", ("chicken_biryani", "paneer_butter_masala", "gulab_jamun")),
    PackageTemplate("signature_nonveg", "signature", "non_veg", ("chicken_biryani", "mutton_biryani", "paneer_butter_masala", "gulab_jamun")),
    PackageTemplate("royal_nonveg", "royal", "non_veg", ("chicken_biryani", "mutton_biryani", "paneer_butter_masala", "live_dosa", "gulab_jamun")),
]
