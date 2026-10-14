"""Dutchie consumer menus (dutchie.com and Dutchie menus embedded in dispensary sites).

Products carry parallel arrays: Options ["1/8oz", "1/4oz"], medicalPrices [45, 85],
medicalSpecialPrices [36, 68] when on sale.
"""

from ..normalize import make_offer, name_of

NAME = "dutchie"


def _looks_like_product(d):
    return (isinstance(d.get("Options"), list)
            and any(isinstance(d.get(k), list) for k in ("Prices", "medicalPrices", "recPrices"))
            and (d.get("Name") or d.get("name")))


def _at(values, index):
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _deal_text(d):
    special = d.get("specialData") or {}
    for key in ("saleSpecials", "bogoSpecials"):
        for item in special.get(key) or []:
            if isinstance(item, dict) and item.get("specialName"):
                return item["specialName"]
    return ""


def parse(store_id, doc, iter_dicts):
    offers = []
    for d in iter_dicts(doc):
        if not _looks_like_product(d):
            continue
        brand = d.get("brandName") or name_of(d.get("brand"))
        options = d["Options"] or [""]
        med = d.get("medicalPrices") or []
        has_med = any(p for p in med if p)
        for i, option in enumerate(options):
            base = next((p for p in (_at(med, i), _at(d.get("Prices"), i), _at(d.get("recPrices"), i)) if p), None)
            sale_list = d.get("medicalSpecialPrices") if has_med else d.get("recSpecialPrices")
            sale = _at(sale_list, i) or _at(d.get("medicalSpecialPrices"), i)
            offer = make_offer(
                store_id=store_id, source=NAME, source_id=d.get("id") or d.get("_id") or "",
                name=d.get("Name") or d.get("name"), brand=brand,
                category_hints=(d.get("type"), d.get("subcategory")),
                strain_type=d.get("strainType"), size_label=option if option != "N/A" else "",
                price=base, sale_price=sale, thc=d.get("THCContent"), cbd=d.get("CBDContent"),
                deal_text=_deal_text(d), image=d.get("Image") or d.get("image") or "",
            )
            if offer:
                offers.append(offer)
    return offers
