"""Sri Sai Raja Caterers — "Amma chethi vanta" — the printed menu, as data.

Nine per-plate packages transcribed from the owner's menu cards. Each package is a fixed
spread plus a few "choose one" slots (the [or] lines on the card). Disposable plates, tissues
and dustbin covers are part of every plate; packaged water is an optional add-on.

Prices on the cards are what the owner charges today. They are kept as `list_price` so the
engine's cost-based number can be judged against them, and so the site can show the printed
price beside the live one. The Justdial market band for the same kind of menu is kept beside
it for the competitive read.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal as D

MENU_VERSION = 3   # bump when dishes or packages change; the loader re-applies on a new version

INCLUDES = ("Disposable plates, glasses & spoons", "Tissues", "Dustbin covers")
OPTIONAL_EXTRAS = ("water",)   # never inside a package price; offered as an add-on


@dataclass(frozen=True)
class Dish:
    slug: str
    name: str
    category: str                 # menu_categories.key
    diet: str = "veg"             # veg | non_veg
    name_te: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    popularity: int = 60


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    options: tuple[str, ...]      # dish slugs; the first is the default


@dataclass(frozen=True)
class Package:
    key: str
    name: str
    tier: str                     # classic | signature | royal (margin shaping + chat presentation)
    diet: str                     # veg | non_veg
    list_price: D                 # per plate, from the printed card
    tagline: str
    description: str
    fixed: tuple[str, ...]
    slots: tuple[Slot, ...] = ()
    occasions: tuple[str, ...] = ()
    sort_order: int = 0
    market_low: D = D("0")        # Justdial band for an equivalent menu, per plate
    market_high: D = D("0")
    includes: tuple[str, ...] = INCLUDES
    margin_adj: D = D("0")        # points on the tier margin; see docs/10-menu.md for how these were set


OVERHEAD_PCT = D("18")            # transport, gas, vessel hire, cooks — on top of food + per-dish labour

# Points each package adds to its tier's margin target, chosen so the engine lands on the
# recommended card at 100 guests on the seed wholesale rates (docs/10-menu.md, "Calibration").
MARGIN_ADJ = {"ssr_veg_classic": 9, "ssr_veg_comfort": 6, "ssr_veg_signature": 0, "ssr_veg_festive": 5, "ssr_veg_grand": 3,
              "ssr_nonveg_chicken": 0, "ssr_nonveg_mutton": -2, "ssr_nonveg_chicken_coastal": -7, "ssr_nonveg_mutton_coastal": -8}


def _d(slug, name, category, diet="veg", te="", desc="", tags=(), pop=60):
    return Dish(slug, name, category, diet, te, desc, tuple(tags), pop)


DISHES: tuple[Dish, ...] = (
    # rice & breads
    _d("veg_biryani", "Veg Dum Biryani", "rice_breads", te="వెజ్ దమ్ బిర్యానీ", desc="Basmati on dum with garden vegetables, mint and fried onion", tags=("hyderabadi",), pop=85),
    _d("bagara_rice", "Bagara Rice", "rice_breads", te="బగారా అన్నం", desc="Ghee-tempered basmati with whole spices", tags=("hyderabadi",), pop=70),
    _d("white_rice", "White Rice", "rice_breads", te="అన్నం", desc="Steamed sona masoori", tags=("staple",), pop=90),
    _d("pulihora", "Pulihora", "rice_breads", te="పులిహోర", desc="Tamarind rice, temple style, with peanuts", tags=("telugu", "traditional"), pop=85),
    _d("puri", "Puri", "rice_breads", te="పూరీ", desc="Puffed wheat puris, fried to order", tags=("bread",), pop=75),
    _d("chapati", "Chapati", "rice_breads", te="చపాతీ", desc="Soft whole-wheat chapatis", tags=("bread",), pop=65),
    _d("phulka", "Phulka", "rice_breads", te="ఫుల్కా", desc="Thin phulkas, brushed with ghee", tags=("bread",), pop=60),
    # curries
    _d("sambar", "Sambar", "main_veg", te="సాంబార్", desc="Drumstick and vegetable sambar", tags=("staple",), pop=90),
    _d("rasam", "Rasam", "main_veg", te="రసం", desc="Pepper-garlic rasam", tags=("staple",), pop=70),
    _d("dal_tadka", "Pappu", "main_veg", te="పప్పు", desc="Toor dal with ghee tempering", tags=("staple",), pop=85),
    _d("majjiga_charu", "Majjiga Charu", "main_veg", te="మజ్జిగ చారు", desc="Spiced buttermilk stew", tags=("telugu", "traditional"), pop=55),
    _d("gutti_vankaya", "Gutti Vankaya Masala", "main_veg", te="గుత్తి వంకాయ", desc="Stuffed brinjal in peanut-sesame gravy", tags=("telugu", "signature"), pop=85),
    _d("alu_masala", "Alu Masala Curry", "main_veg", te="ఆలూ మసాలా", desc="Potato in onion-tomato masala", tags=("crowd_pleaser",), pop=75),
    _d("alu_tomato_curry", "Alu Tomato Curry", "main_veg", te="ఆలూ టమాటా కూర", desc="Potato and tomato, home style", tags=("crowd_pleaser",), pop=70),
    _d("paneer_butter_masala", "Paneer Butter Masala", "main_veg", te="పనీర్ బటర్ మసాలా", desc="Rich tomato-cashew gravy", tags=("north_indian", "crowd_pleaser"), pop=95),
    _d("chole_masala", "Chole Masala", "main_veg", te="చోలే మసాలా", desc="Kabuli chana in a slow onion-tomato masala", tags=("north_indian",), pop=70),
    _d("dondakaya_fry", "Dondakaya Fry", "main_veg", te="దొండకాయ వేపుడు", desc="Ivy gourd fry", tags=("telugu",), pop=70),
    _d("bendakaya_fry", "Bendakaya Fry", "main_veg", te="బెండకాయ వేపుడు", desc="Crisp okra fry", tags=("telugu",), pop=70),
    # chutneys & sides
    _d("gongura_chutney", "Gongura Chutney", "sides", te="గోంగూర పచ్చడి", desc="Sorrel-leaf chutney, the Andhra classic", tags=("telugu", "signature"), pop=85),
    _d("vankaya_dosakaya_chutney", "Vankaya + Dosakaya Chutney", "sides", te="వంకాయ దోసకాయ పచ్చడి", desc="Brinjal and cucumber chutney", tags=("telugu",), pop=70),
    _d("papad", "Papad", "sides", te="అప్పడం", desc="Crisp fried papad", tags=("staple",), pop=80),
    _d("curd", "Curd", "sides", te="పెరుగు", desc="Set curd", tags=("staple",), pop=85),
    _d("raita", "Raita", "sides", te="రైతా", desc="Onion-tomato raita", tags=("staple",), pop=80),
    _d("salad", "Salad", "sides", te="సలాడ్", desc="Onion, tomato, lemon", tags=("staple",), pop=70),
    _d("karapodi_ghee", "Karapodi & Ghee", "sides", te="కారప్పొడి & నెయ్యి", desc="Gunpowder with ghee", tags=("telugu", "traditional"), pop=65),
    _d("meetha_paan", "Meetha Paan", "sides", te="మీఠా పాన్", desc="Sweet paan to finish", tags=("traditional",), pop=70),
    # starters
    _d("mirchi_bajji", "Mirchi Bajji", "starters", te="మిర్చి బజ్జి", desc="Stuffed chilli bajji, Hyderabad street classic", tags=("hyderabadi", "traditional"), pop=85),
    _d("vada", "Vada", "starters", te="గారెలు", desc="Urad dal garelu", tags=("telugu", "traditional"), pop=70),
    _d("masala_vada", "Masala Vada", "starters", te="మసాలా వడ", desc="Crisp chana-dal vada with onion", tags=("telugu",), pop=75),
    _d("alu_65", "Alu 65", "starters", te="ఆలూ 65", desc="Crisp potato 65", tags=("crowd_pleaser", "kids"), pop=70),
    _d("cauliflower_65", "Cauliflower 65", "starters", te="గోబీ 65", desc="Gobi 65, curry-leaf tempered", tags=("crowd_pleaser",), pop=70),
    _d("chicken_fry", "Chicken Fry", "starters", "non_veg", te="చికెన్ వేపుడు", desc="Andhra-style dry chicken fry", tags=("telugu", "spicy"), pop=90),
    _d("fish_fry", "Fish Fry", "starters", "non_veg", te="చేపల వేపుడు", desc="Marinated fish, pan-fried", tags=("coastal",), pop=80),
    _d("prawns_fry", "Prawns Fry", "starters", "non_veg", te="రొయ్యల వేపుడు", desc="Prawns tossed dry with spices", tags=("coastal", "premium"), pop=75),
    # non-veg mains
    _d("chicken_biryani", "Chicken Dum Biryani", "main_nonveg", "non_veg", te="చికెన్ దమ్ బిర్యానీ", desc="Hyderabadi kacchi dum, halal", tags=("hyderabadi", "signature"), pop=100),
    _d("mutton_biryani", "Mutton Dum Biryani", "main_nonveg", "non_veg", te="మటన్ దమ్ బిర్యానీ", desc="Slow dum with tender mutton, halal", tags=("hyderabadi", "premium", "mutton"), pop=95),
    _d("chicken_curry", "Chicken Curry", "main_nonveg", "non_veg", te="కోడి కూర", desc="Home-style chicken curry", tags=("telugu",), pop=85),
    _d("mutton_curry", "Mutton Curry", "main_nonveg", "non_veg", te="మటన్ కూర", desc="Slow-cooked mutton curry", tags=("telugu", "mutton"), pop=85),
    _d("prawns_curry", "Prawns Curry", "main_nonveg", "non_veg", te="రొయ్యల కూర", desc="Prawns in a coconut-tamarind gravy", tags=("coastal", "premium"), pop=75),
    # sweets
    _d("purnalu", "Purnalu", "desserts", te="పూర్ణాలు", desc="Jaggery-chana dal dumplings in a crisp batter", tags=("telugu", "traditional"), pop=75),
    _d("bobbatlu", "Bobbatlu", "desserts", te="బొబ్బట్లు", desc="Sweet stuffed flatbread with ghee", tags=("telugu", "traditional"), pop=75),
    _d("double_ka_meetha", "Double ka Meetha", "desserts", te="డబుల్ కా మీఠా", desc="Hyderabadi bread pudding with saffron", tags=("hyderabadi", "traditional"), pop=85),
    _d("gulab_jamun", "Gulab Jamun", "desserts", te="గులాబ్ జామూన్", desc="Soft, warm, in cardamom syrup", tags=("classic",), pop=95),
    _d("rava_kesari", "Rava Kesari", "desserts", te="రవ్వ కేసరి", desc="Saffron semolina halwa", tags=("traditional",), pop=65),
    _d("chakkara_pongali", "Chakkara Pongali", "desserts", te="చక్కెర పొంగలి", desc="Jaggery rice pongal with ghee", tags=("telugu", "traditional"), pop=65),
    _d("vanilla_ice_cream", "Vanilla Ice Cream", "desserts", te="వనిల్లా ఐస్ క్రీం", desc="Scoop of vanilla", tags=("kids",), pop=80),
    _d("butterscotch_ice_cream", "Butterscotch Ice Cream", "desserts", te="బటర్‌స్కాచ్ ఐస్ క్రీం", desc="Scoop of butterscotch", tags=("kids",), pop=75),
    _d("fruit_salad", "Fruit Salad", "desserts", te="ఫ్రూట్ సలాడ్", desc="Seasonal cut fruit", tags=("healthy",), pop=65),
    # service
    _d("disposables", "Disposables, tissues & bin covers", "service", te="డిస్పోజబుల్స్", desc="Plates, glasses, spoons, tissues and dustbin covers", tags=("included",), pop=0),
    _d("water", "Packaged drinking water", "service", te="వాటర్ బాటిల్", desc="500 ml sealed bottle per guest", tags=("optional",), pop=0),
)

DISH_BY_SLUG = {d.slug: d for d in DISHES}

_SWEET_V1 = Slot("sweet", "Sweet", ("purnalu", "double_ka_meetha", "gulab_jamun"))
_SNACK_V1 = Slot("snack", "Snack", ("mirchi_bajji", "vada", "masala_vada"))
_SNACK = Slot("snack", "Snack", ("mirchi_bajji", "masala_vada"))
_SWEET_NV = Slot("sweet", "Sweet", ("gulab_jamun", "double_ka_meetha"))
_NV_BASE = ("white_rice", "sambar", "rasam", "gutti_vankaya", "chicken_fry", "curd", "raita", "salad", "vanilla_ice_cream", "disposables")

PACKAGES: tuple[Package, ...] = (
    Package("ssr_veg_classic", "Classic Veg", "classic", "veg", D("185"), "The everyday feast.",
            "Veg dum biryani, pulihora, two curries, a fry, a chutney, a sweet and a snack — the spread every Telugu function is built on.",
            ("veg_biryani", "white_rice", "pulihora", "sambar", "dal_tadka", "papad", "curd", "raita", "disposables"),
            (Slot("curry", "Curry", ("gutti_vankaya", "alu_masala")), Slot("fry", "Fry", ("dondakaya_fry", "bendakaya_fry")),
             Slot("chutney", "Chutney", ("gongura_chutney", "vankaya_dosakaya_chutney")), _SWEET_V1, _SNACK_V1),
            ("pooja", "housewarming", "naming_ceremony", "birthday"), 10, D("250"), D("300")),
    Package("ssr_veg_comfort", "Comfort Veg", "classic", "veg", D("205"), "Classic, plus paneer, puri and ice cream.",
            "Adds paneer butter masala, both chutneys, puri and vanilla ice cream to the Classic spread.",
            ("veg_biryani", "white_rice", "pulihora", "sambar", "dal_tadka", "paneer_butter_masala", "dondakaya_fry", "gongura_chutney",
             "vankaya_dosakaya_chutney", "papad", "curd", "raita", "puri", "vanilla_ice_cream", "disposables"),
            (), ("housewarming", "birthday", "anniversary"), 20, D("250"), D("320")),
    Package("ssr_veg_signature", "Signature Veg", "signature", "veg", D("235"), "The one most families choose.",
            "Paneer, a second curry, a 65-style fry, a traditional sweet, a snack, bread, ice cream and meetha paan.",
            ("veg_biryani", "white_rice", "pulihora", "sambar", "dal_tadka", "paneer_butter_masala", "vankaya_dosakaya_chutney", "papad", "curd",
             "raita", "meetha_paan", "vanilla_ice_cream", "disposables"),
            (Slot("curry", "Second curry", ("chole_masala", "alu_tomato_curry")), Slot("fry", "Fry", ("alu_65", "cauliflower_65", "dondakaya_fry")),
             Slot("sweet", "Sweet", ("purnalu", "bobbatlu", "double_ka_meetha")), _SNACK, Slot("bread", "Bread", ("puri", "chapati"))),
            ("housewarming", "half_saree", "birthday", "anniversary", "pooja"), 30, D("280"), D("350")),
    Package("ssr_veg_festive", "Festive Veg", "signature", "veg", D("265"), "Two chutneys, karapodi, four-way sweet.",
            "Bagara rice or biryani, paneer and alu-tomato curries, both chutneys, karapodi, a choice of four sweets, puri, ice cream and paan.",
            ("white_rice", "pulihora", "sambar", "dal_tadka", "paneer_butter_masala", "alu_tomato_curry", "dondakaya_fry", "vankaya_dosakaya_chutney",
             "gongura_chutney", "papad", "karapodi_ghee", "curd", "raita", "puri", "meetha_paan", "vanilla_ice_cream", "disposables"),
            (Slot("rice", "Rice", ("veg_biryani", "bagara_rice")), Slot("sweet", "Sweet", ("purnalu", "bobbatlu", "gulab_jamun", "rava_kesari")), _SNACK),
            ("wedding", "engagement", "half_saree", "festival_party"), 40, D("300"), D("400")),
    Package("ssr_veg_grand", "Grand Veg", "royal", "veg", D("305"), "Twenty-two items. Two sweets. Nothing to add.",
            "Paneer and chole, two fries, two chutneys, purnalu and chakkara pongali, butterscotch ice cream, fruit salad, majjiga charu, karapodi & ghee, puri and phulka.",
            ("veg_biryani", "white_rice", "pulihora", "sambar", "paneer_butter_masala", "chole_masala", "bendakaya_fry", "dondakaya_fry", "gongura_chutney",
             "vankaya_dosakaya_chutney", "purnalu", "chakkara_pongali", "butterscotch_ice_cream", "papad", "curd", "raita", "meetha_paan", "karapodi_ghee",
             "majjiga_charu", "fruit_salad", "puri", "phulka", "disposables"),
            (), ("wedding", "reception", "engagement", "corporate"), 50, D("350"), D("450")),
    Package("ssr_nonveg_chicken", "Chicken Dum", "classic", "non_veg", D("315"), "Chicken dum biryani with mutton curry.",
            "Chicken dum biryani, mutton curry, chicken fry, sambar, rasam, gutti vankaya, a sweet, a snack, curd, raita, salad and ice cream.",
            ("chicken_biryani", "mutton_curry") + _NV_BASE, (_SWEET_NV, _SNACK),
            ("birthday", "festival_party", "housewarming", "corporate"), 60, D("350"), D("450")),
    Package("ssr_nonveg_mutton", "Mutton Dum", "signature", "non_veg", D("315"), "Mutton dum biryani with chicken curry.",
            "Mutton dum biryani, chicken curry, chicken fry, sambar, rasam, gutti vankaya, a sweet, a snack, curd, raita, salad and ice cream.",
            ("mutton_biryani", "chicken_curry") + _NV_BASE, (_SWEET_NV, _SNACK),
            ("wedding", "reception", "engagement", "anniversary"), 70, D("400"), D("550")),
    Package("ssr_nonveg_chicken_coastal", "Chicken Dum · Coastal", "signature", "non_veg", D("365"), "Chicken Dum, plus fish and prawns.",
            "The Chicken Dum spread with fish fry and a prawns curry or fry.",
            ("chicken_biryani", "mutton_curry", "fish_fry") + _NV_BASE, (Slot("prawns", "Prawns", ("prawns_curry", "prawns_fry")), _SWEET_NV, _SNACK),
            ("birthday", "festival_party", "corporate", "bachelor_party"), 80, D("450"), D("600")),
    Package("ssr_nonveg_mutton_coastal", "Mutton Dum · Coastal", "royal", "non_veg", D("365"), "Mutton dum, fish and prawns. The full table.",
            "The Mutton Dum spread with fish fry and a prawns curry or fry.",
            ("mutton_biryani", "chicken_curry", "fish_fry") + _NV_BASE, (Slot("prawns", "Prawns", ("prawns_curry", "prawns_fry")), _SWEET_NV, _SNACK),
            ("wedding", "reception", "engagement", "corporate"), 90, D("500"), D("700")),
)

PACKAGES = tuple(Package(**{**p.__dict__, "margin_adj": D(MARGIN_ADJ.get(p.key, 0))}) for p in PACKAGES)
PACKAGE_BY_KEY = {p.key: p for p in PACKAGES}


def default_slugs(p: Package) -> list[str]:
    """The plate as printed: fixed items plus each slot's first option."""
    return list(p.fixed) + [s.options[0] for s in p.slots]


def all_slugs(p: Package) -> set[str]:
    return set(p.fixed) | {o for s in p.slots for o in s.options}
