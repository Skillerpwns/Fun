"""Jane (iheartjane.com) menus, which are served from an Algolia search index.

Each product has one price field per size (price_gram, price_eighth_ounce, ...) and a
matching discounted_price_* field when it's on special.
"""

from ..normalize import format_size, make_offer, name_of

NAME = "jane"

SIZE_FIELDS = [
    ("half_gram", 0.5), ("gram", 1.0), ("two_gram", 2.0), ("eighth_ounce", 3.5),
    ("quarter_ounce", 7.0), ("half_ounce", 14.0), ("ounce", 28.0), ("each", None),
]


def _looks_like_product(d):
    return d.get("name") and "kind" in d and any(f"price_{size}" in d for size, _ in SIZE_FIELDS)


def parse(store_id, doc, iter_dicts):
    offers = []
    for d in iter_dicts(doc):
        if not _looks_like_product(d):
            continue
        images = d.get("image_urls") or d.get("photos") or []
        image = images[0] if images and isinstance(images[0], str) else ""
        deal = d.get("special_title") or ""
        if not deal and isinstance(d.get("applicable_special_titles"), list) and d["applicable_special_titles"]:
            deal = d["applicable_special_titles"][0]
        for size, grams in SIZE_FIELDS:
            price = d.get(f"price_{size}")
            if not price:
                continue
            label = format_size(grams) if grams else (d.get("amount") or d.get("net_weight_grams") or "")
            offer = make_offer(
                store_id=store_id, source=NAME,
                source_id=d.get("product_id") or d.get("menu_product_id") or d.get("objectID") or "",
                name=d.get("name"), brand=name_of(d.get("brand")),
                category_hints=(d.get("kind"), d.get("kind_subtype"), d.get("root_subtype")),
                strain_type=d.get("category"), size_label=str(label), weight_g=grams,
                price=price, sale_price=d.get(f"discounted_price_{size}"),
                thc=d.get("percent_thc"), cbd=d.get("percent_cbd"), deal_text=deal, image=image,
            )
            if offer:
                offers.append(offer)
    return offers
