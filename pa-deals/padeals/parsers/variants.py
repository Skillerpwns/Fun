"""Menus where each product has a list of size variants, each with its own price.

Covers Dutchie Plus (variants: option / priceMed / specialPriceMed), Sweed
(variants: unitSize / price / promoPrice) and similar storefronts.
"""

from ..normalize import clean_text, make_offer, name_of, to_float

NAME = "variants"

PRICE_KEYS = ["priceMed", "medPrice", "medicalPrice", "price", "priceRec", "recPrice", "basePrice", "listPrice"]
SALE_KEYS = ["specialPriceMed", "salePriceMed", "promoPrice", "salePrice", "specialPrice", "discountedPrice",
             "specialPriceRec", "finalPrice"]
SIZE_KEYS = ["option", "name", "size", "weight", "label", "title"]


def _first(d, keys):
    for key in keys:
        value = d.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _price(value):
    if isinstance(value, dict):
        value = _first(value, ["amount", "value", "price"])
    return to_float(value)


def _size_label(variant):
    unit = variant.get("unitSize")
    if isinstance(unit, dict) and unit.get("value") is not None:
        return f"{unit.get('value')}{unit.get('unitAbbr') or unit.get('unit') or ''}"
    return clean_text(_first(variant, SIZE_KEYS) or "")


def _looks_like_product(d):
    variants = d.get("variants")
    return (isinstance(variants, list) and variants and isinstance(variants[0], dict)
            and _first(d, ["name", "productName", "title"])
            and any(_first(v, PRICE_KEYS) is not None for v in variants if isinstance(v, dict)))


def _potency(d, variant, which):
    for source in (variant, d):
        for key in (f"potency{which.capitalize()}", f"{which}Content", which, f"{which}_percent", f"percent_{which}"):
            if source.get(key) not in (None, ""):
                return source[key]
        tests = source.get("labTests")
        if isinstance(tests, dict) and tests.get(which) is not None:
            return tests[which]
    return None


def parse(store_id, doc, iter_dicts):
    offers = []
    for d in iter_dicts(doc):
        if not _looks_like_product(d):
            continue
        name = _first(d, ["name", "productName", "title"])
        brand = name_of(d.get("brand") or d.get("brandName"))
        strain = d.get("strainType")
        if not strain and isinstance(d.get("strain"), dict):
            strain = d["strain"].get("prevalence") or d["strain"].get("name")
        image = d.get("image") or name_of(d.get("images"))
        if isinstance(image, dict):
            image = image.get("url") or ""
        for v in d["variants"]:
            if not isinstance(v, dict):
                continue
            offer = make_offer(
                store_id=store_id, source=NAME, source_id=d.get("id") or d.get("_id") or "",
                name=name, brand=brand,
                category_hints=(name_of(d.get("category")), name_of(d.get("subcategory")), d.get("productType")),
                strain_type=name_of(strain), size_label=_size_label(v),
                price=_price(_first(v, PRICE_KEYS)), sale_price=_price(_first(v, SALE_KEYS)),
                thc=_potency(d, v, "thc"), cbd=_potency(d, v, "cbd"),
                image=image if isinstance(image, str) else "",
            )
            if offer:
                offers.append(offer)
    return offers
