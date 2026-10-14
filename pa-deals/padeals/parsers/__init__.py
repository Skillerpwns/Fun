"""Pull product offers out of the JSON a menu page loaded.

Each parser recognizes one platform's product shape anywhere in a JSON document, so it
works no matter which URL or wrapper the data came in. The generic parser is a fallback
for menus on platforms we don't know yet.
"""

from . import dutchie, generic, jane, variants

PLATFORM_PARSERS = [dutchie, jane, variants]


def iter_dicts(node, depth=0):
    """Yield every dict nested anywhere inside a JSON value."""
    if depth > 40:
        return
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_dicts(value, depth + 1)
    elif isinstance(node, list):
        for value in node:
            yield from iter_dicts(value, depth + 1)


def extract_offers(store_id, captures):
    """Return (offers, platforms_seen) from a list of captured {"url", "json"} responses."""
    offers = []
    platforms = set()
    for parser in PLATFORM_PARSERS:
        found = []
        for capture in captures:
            found.extend(parser.parse(store_id, capture["json"], iter_dicts))
        if found:
            platforms.add(parser.NAME)
            offers.extend(found)
    if not offers:
        for capture in captures:
            offers.extend(generic.parse(store_id, capture["json"], iter_dicts))
        if offers:
            platforms.add(generic.NAME)
    return dedupe(offers), sorted(platforms)


def count_products(json_doc):
    """How many products a single JSON response holds (used to spot the menu's data request)."""
    total = 0
    for parser in PLATFORM_PARSERS:
        total += len(parser.parse("_", json_doc, iter_dicts))
    return total


def dedupe(offers):
    """The same product often arrives in several responses (first page, replayed pages, search)."""
    seen = {}
    for offer in offers:
        key = (offer["source"], offer["source_id"] or offer["name"].lower(), offer["brand"].lower(),
               offer["weight_g"], offer["size"].lower())
        if key not in seen:
            seen[key] = offer
    return list(seen.values())
