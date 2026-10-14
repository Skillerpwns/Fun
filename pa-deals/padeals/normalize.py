"""Turn messy menu data into consistent fields: category, weight, THC, price per gram."""

import math
import re

# Dispensaries round an ounce down to 28 g, so an eighth is 3.5 g.
OUNCE_G = 28.0

CATEGORIES = ["flower", "preroll", "vape", "concentrate", "edible", "tincture", "capsule", "topical", "other"]

# Checked in order, so more specific words come first ("live resin cart" is a vape,
# "pre-roll" is not plain flower).
_CATEGORY_KEYWORDS = [
    ("preroll", ["pre-roll", "preroll", "pre roll", "prerolls", "pre-rolls", "joint", "blunt"]),
    ("vape", ["vape", "vaporizer", "vaporizers", "cartridge", "cart", "pod", "disposable", "510"]),
    ("concentrate", ["concentrate", "extract", "wax", "shatter", "rosin", "resin", "badder", "budder",
                     "sugar", "diamonds", "sauce", "crumble", "kief", "hash", "rso", "dab"]),
    ("flower", ["flower", "bud", "buds", "smalls", "shake", "ground", "popcorn", "dry leaf"]),
    ("edible", ["edible", "gummy", "gummies", "chocolate", "troche", "lozenge", "chew", "beverage"]),
    ("tincture", ["tincture", "oral", "sublingual", "syringe", "drops"]),
    ("capsule", ["capsule", "capsules", "tablet", "tablets", "pill", "softgel"]),
    ("topical", ["topical", "lotion", "balm", "cream", "salve", "transdermal", "patch"]),
]

# Price-per-gram only makes sense for these; edibles and tinctures are sold by dose.
PER_GRAM_CATEGORIES = {"flower", "preroll", "vape", "concentrate"}


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def name_of(value):
    """Platforms give brands/categories either as a string or as {"name": ...}."""
    if isinstance(value, dict):
        return clean_text(value.get("name") or value.get("title") or "")
    if isinstance(value, (list, tuple)):
        return name_of(value[0]) if value else ""
    return clean_text(value)


def norm_key(value):
    """Lowercase alphanumerics only, for matching names across runs and stores."""
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def to_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def category_of(*hints):
    """Map platform category labels (and product names as a fallback) to our categories."""
    for hint in hints:
        text = " " + norm_key(hint) + " "
        if not text.strip():
            continue
        for category, words in _CATEGORY_KEYWORDS:
            for word in words:
                word = norm_key(word)
                if f" {word} " in text or f" {word}s " in text:
                    return category
    return "other"


def strain_type_of(value):
    text = norm_key(value)
    if not text:
        return ""
    if "cbd" in text:
        return "cbd"
    if "indica" in text and "sativa" in text:
        return "hybrid"
    for kind in ("indica", "sativa", "hybrid"):
        if kind in text:
            return kind
    return ""


_FRACTION_OZ = re.compile(r"(\d+)\s*/\s*(\d+)\s*(?:th\b|oz\b|ounce)", re.I)
_AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|milligrams?|g|grams?|gr|oz|ounces?)\b", re.I)
_WORDS = [
    ("half ounce", OUNCE_G / 2), ("half oz", OUNCE_G / 2), ("quarter", OUNCE_G / 4),
    ("eighth", OUNCE_G / 8), ("ounce", OUNCE_G),
]


def parse_weight_g(text, category=None):
    """Weight in grams from a size label like '1/8oz', '3.5g', '0.5 g', '500mg', 'Eighth'.

    Milligrams only count as weight for vapes/concentrates; on edibles and tinctures
    'mg' is the THC dose, not the product weight.
    """
    raw = clean_text(text).lower()
    if not raw:
        return None
    fraction = _FRACTION_OZ.search(raw)
    if fraction:
        num, den = int(fraction.group(1)), int(fraction.group(2))
        if den:
            return round(OUNCE_G * num / den, 3)
    amount = _AMOUNT.search(raw)
    if amount:
        value = float(amount.group(1))
        unit = amount.group(2).lower()
        if unit.startswith("m"):
            if category in ("vape", "concentrate", "preroll", "flower"):
                return round(value / 1000.0, 3)
            return None
        if unit.startswith("o"):
            return round(value * OUNCE_G, 3)
        return value
    for word, grams in _WORDS:
        if word in raw:
            return grams
    return None


def format_size(grams):
    if grams is None:
        return ""
    for label, value in (("1/8 oz", 3.5), ("1/4 oz", 7.0), ("1/2 oz", 14.0), ("1 oz", 28.0)):
        if abs(grams - value) < 0.01:
            return f"{label} ({value:g}g)"
    return f"{grams:g}g"


def price_per_gram(price, grams, category):
    if not price or not grams or category not in PER_GRAM_CATEGORIES:
        return None
    return round(price / grams, 2)


_SIZE_IN_NAME = re.compile(
    r"(\[[^\]]*\]|\([^)]*\)|\b\d+(?:\.\d+)?\s*(?:mg|g|gr|grams?|oz)\b|\b\d+\s*/\s*\d+\s*(?:oz)?\b)", re.I)
_FORM_WORDS = re.compile(
    r"\b(flower|smalls|pre-?rolls?|vape|cart(?:ridge)?|disposable|pod|live resin|live rosin|cured resin|"
    r"distillate|badder|budder|sugar|shatter|wax|diamonds|sauce|rso|indica|sativa|hybrid|whole|ground)\b", re.I)


def strain_guess(name, brand=""):
    """Best-effort strain name: drop the brand, sizes, and product-form words from the title."""
    text = clean_text(name)
    if brand:
        text = re.sub(re.escape(clean_text(brand)), " ", text, flags=re.I)
    text = _SIZE_IN_NAME.sub(" ", text)
    text = _FORM_WORDS.sub(" ", text)
    text = re.sub(r"\s*[|•·:\-–—]\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -|")
    return text or clean_text(name)


def thc_percent(value):
    """THC as a percent from a number, '22.5%', or a {range: [...], unit: ...} object."""
    if isinstance(value, dict):
        unit = str(value.get("unit") or value.get("unitAbbr") or "").lower()
        if unit and "percent" not in unit and unit != "%":
            return None
        values = value.get("range") or value.get("value") or value.get("values")
        if isinstance(values, list):
            nums = [to_float(v) for v in values if to_float(v) is not None]
            return max(nums) if nums else None
        return thc_percent(values)
    if isinstance(value, list):
        nums = [thc_percent(v) for v in value]
        nums = [n for n in nums if n is not None]
        return max(nums) if nums else None
    if isinstance(value, str) and "mg" in value.lower():
        return None
    number = to_float(value)
    if number is None or number <= 0 or number > 100:
        return None
    return round(number, 2)


def make_offer(*, store_id, source, name, brand="", category_hints=(), strain_type="", size_label="",
               weight_g=None, price=None, sale_price=None, thc=None, cbd=None, deal_text="",
               image="", source_id="", url=""):
    """Build one normalized offer (a product at one size at one store). Returns None if unusable."""
    name = clean_text(name)
    price = to_float(price)
    sale_price = to_float(sale_price)
    if not name or not price or price <= 0:
        return None
    category = category_of(*category_hints, name)
    if weight_g is None:
        weight_g = parse_weight_g(size_label, category) or parse_weight_g(name, category)
    on_sale = sale_price is not None and 0 < sale_price < price - 0.004
    current = sale_price if on_sale else price
    brand = clean_text(brand)
    return {
        "store_id": store_id,
        "source": source,
        "source_id": clean_text(source_id),
        "name": name,
        "brand": brand,
        "strain": strain_guess(name, brand),
        "category": category,
        "strain_type": strain_type_of(strain_type),
        "size": format_size(weight_g) or clean_text(size_label),
        "weight_g": weight_g,
        "price": round(current, 2),
        "original_price": round(price, 2) if on_sale else None,
        "discount_pct": round(100 * (price - current) / price) if on_sale else 0,
        "price_per_g": price_per_gram(current, weight_g, category),
        "thc": thc_percent(thc),
        "cbd": thc_percent(cbd),
        "deal": clean_text(deal_text),
        "image": clean_text(image),
        "url": clean_text(url),
    }


def offer_key(offer):
    """Stable identity for an offer across runs: same store, brand, product name and size."""
    size = f"{offer['weight_g']:g}g" if offer.get("weight_g") else norm_key(offer.get("size"))
    return "|".join([offer["store_id"], norm_key(offer.get("brand")), norm_key(offer["name"]), size])
