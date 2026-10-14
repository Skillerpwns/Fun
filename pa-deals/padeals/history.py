"""Remembers what each store carried and at what price, to flag new items and price drops."""

import json
from datetime import datetime, timedelta, timezone

from .normalize import offer_key

NEW_FOR = timedelta(hours=48)       # how long a new arrival keeps its NEW badge
DROP_FOR = timedelta(days=7)        # how long a price cut keeps its badge
BACK_AFTER = timedelta(days=3)      # gone this long and returned = "back in stock"
FORGET_AFTER = timedelta(days=60)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _age(stamp, now):
    if not stamp:
        return None
    return now - datetime.fromisoformat(stamp)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save(path, history, now):
    now_dt = datetime.fromisoformat(now)
    kept = {k: v for k, v in history.items() if _age(v.get("last_seen"), now_dt) < FORGET_AFTER}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kept, f, separators=(",", ":"))


def annotate(offers, history, now):
    """Add first_seen / is_new / back_in_stock / price_drop_from to fresh offers; update history."""
    now_dt = datetime.fromisoformat(now)
    known_stores = {entry.get("store_id") for entry in history.values()}
    for offer in offers:
        key = offer_key(offer)
        entry = history.get(key)
        back = False
        if entry is None:
            # A store's very first scrape is the baseline: none of it counts as "new".
            entry = history[key] = {"store_id": offer["store_id"], "first_seen": now, "last_seen": now,
                                    "price": offer["price"], "previous_price": None, "price_changed_at": None,
                                    "new": offer["store_id"] in known_stores}
        else:
            back = _age(entry["last_seen"], now_dt) > BACK_AFTER
            if abs(entry["price"] - offer["price"]) >= 0.01:
                entry["previous_price"], entry["price"], entry["price_changed_at"] = entry["price"], offer["price"], now
        entry["last_seen"] = now
        changed = _age(entry.get("price_changed_at"), now_dt)
        offer["first_seen"] = entry["first_seen"]
        offer["is_new"] = bool(entry.get("new")) and _age(entry["first_seen"], now_dt) < NEW_FOR
        offer["back_in_stock"] = back
        offer["price_drop_from"] = (entry["previous_price"]
                                    if entry.get("previous_price") and entry["previous_price"] > offer["price"]
                                    and changed is not None and changed < DROP_FOR else None)
    return offers
