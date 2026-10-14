"""Synthetic menu data shaped like each platform's responses, for tests only.

These are not real products or prices. They mirror the field names the parsers expect,
so the tests check our parsing and paging logic, not what live menus currently return.
"""

CATEGORIES = ["Flower", "Vaporizers", "Concentrate", "Pre-Rolls", "Tincture"]
JANE_KINDS = ["flower", "vape", "extract", "pre-roll", "tincture"]


def dutchie_product(i):
    category = CATEGORIES[i % len(CATEGORIES)]
    options = ["1/8oz", "1/4oz"] if category == "Flower" else ["1g"]
    prices = [40 + i % 10, 75 + i % 10][: len(options)]
    product = {
        "id": f"d{i}", "Name": f"Test Strain {i}", "brandName": f"Brand {i % 4}", "type": category,
        "strainType": ["Indica", "Sativa", "Hybrid"][i % 3], "Options": options,
        "Prices": prices, "medicalPrices": prices, "recPrices": [],
        "THCContent": {"unit": "PERCENTAGE", "range": [18 + i % 10]},
        "Image": f"https://example.test/{i}.jpg",
    }
    if i % 5 == 0:
        product["medicalSpecialPrices"] = [round(p * 0.8, 2) for p in prices]
        product["special"] = True
        product["specialData"] = {"saleSpecials": [{"specialName": "20% off Test Brand"}]}
    return product


def dutchie_catalog(count=57):
    return [dutchie_product(i) for i in range(count)]


def dutchie_response(products):
    return {"data": {"filteredProducts": {"products": products, "queryInfo": {"totalCount": len(products)}}}}


def jane_hit(i, store_id=7):
    kind = JANE_KINDS[i % len(JANE_KINDS)]
    hit = {
        "objectID": f"j{i}", "product_id": 1000 + i, "store_id": store_id, "name": f"Jane Strain {i}",
        "brand": f"Jane Brand {i % 3}", "kind": kind, "category": ["indica", "sativa", "hybrid"][i % 3],
        "percent_thc": 20 + i % 8, "image_urls": [f"https://example.test/j{i}.jpg"],
    }
    if kind == "flower":
        hit.update(price_eighth_ounce=45, price_quarter_ounce=85)
        if i % 4 == 0:
            hit.update(discounted_price_eighth_ounce=36, special_title="Flower Friday")
    else:
        hit.update(price_gram=50)
    return hit


def jane_catalog(count=43, store_id=7):
    return [jane_hit(i, store_id) for i in range(count)]


def variants_product(i):
    return {
        "id": f"v{i}", "name": f"Plus Strain {i}", "brand": {"name": "Plus Brand"}, "category": "FLOWER",
        "strainType": "HYBRID", "potencyThc": {"formatted": "21%", "range": [21], "unit": "PERCENTAGE"},
        "variants": [{"option": "3.5g", "priceMed": 50, "priceRec": 55, "specialPriceMed": 42},
                     {"option": "7g", "priceMed": 90, "priceRec": 95}],
    }
