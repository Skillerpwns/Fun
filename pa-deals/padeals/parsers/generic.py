"""Fallback for menu platforms we have no parser for.

Looks for lists of 3+ objects that each have a product name and a price. Results are
rougher (sizes come from the product name), but they beat an empty store.
"""

from ..normalize import make_offer, name_of, to_float

NAME = "generic"

NAME_KEYS = ["name", "Name", "productName", "product_name", "title"]
PRICE_KEYS = ["price", "Price", "medPrice", "priceMed", "medical_price", "unit_price", "unitPrice", "basePrice",
              "regularPrice", "listPrice"]
SALE_KEYS = ["salePrice", "sale_price", "specialPrice", "discountedPrice", "discounted_price", "promoPrice"]
SIZE_KEYS = ["size", "weight", "unit", "option", "amount", "netWeight", "net_weight"]
CATEGORY_KEYS = ["category", "type", "kind", "productType", "product_type", "productCategory"]
BRAND_KEYS = ["brand", "brandName", "brand_name", "vendor", "manufacturer"]


def _first(d, keys):
    for key in keys:
        if d.get(key) not in (None, "", [], {}):
            return d[key]
    return None


def _is_product(d):
    name = _first(d, NAME_KEYS)
    price = _first(d, PRICE_KEYS)
    if isinstance(price, dict):
        price = _first(price, ["amount", "value"])
    return isinstance(name, str) and to_float(price) is not None


def parse(store_id, doc, iter_dicts):
    offers = []
    for d in iter_dicts({"_root": doc}):  # wrap so a top-level JSON array is checked too
        for value in d.values():
            if not (isinstance(value, list) and len(value) >= 3):
                continue
            items = [v for v in value if isinstance(v, dict) and _is_product(v)]
            if len(items) < 3 or len(items) < len(value) * 0.6:
                continue
            for item in items:
                price = _first(item, PRICE_KEYS)
                if isinstance(price, dict):
                    price = _first(price, ["amount", "value"])
                offer = make_offer(
                    store_id=store_id, source=NAME, source_id=item.get("id") or item.get("_id") or "",
                    name=_first(item, NAME_KEYS), brand=name_of(_first(item, BRAND_KEYS)),
                    category_hints=(name_of(_first(item, CATEGORY_KEYS)),),
                    strain_type=name_of(item.get("strainType") or item.get("strain_type") or item.get("strain")),
                    size_label=name_of(_first(item, SIZE_KEYS)), price=price,
                    sale_price=_first(item, SALE_KEYS),
                    thc=item.get("thc") or item.get("thcPercent") or item.get("percent_thc"),
                )
                if offer:
                    offers.append(offer)
    return offers
