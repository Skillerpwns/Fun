"""Combine fresh scrape results with the previous menu.json and write the file the site reads."""

import json
import os

from . import history
from .config import DATA_DIR, store_distance


def load_previous(data_dir=DATA_DIR):
    path = os.path.join(data_dir, "menu.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"stores": [], "products": []}


def build(config, results, now, data_dir=DATA_DIR):
    """results: {store_id: {"error", "offers", "platforms"}} for the stores scraped this run."""
    previous = load_previous(data_dir)
    history_path = os.path.join(data_dir, "history.json")
    prev_stores = {s["id"]: s for s in previous.get("stores", [])}
    prev_products = {}
    for product in previous.get("products", []):
        prev_products.setdefault(product["store_id"], []).append(product)

    seen = history.load(history_path)
    stores_out, products_out = [], []
    for store in config["stores"]:
        sid = store["id"]
        result = results.get(sid)
        if result is None and sid not in prev_stores:
            continue  # never scraped and not part of this run
        info = {
            "id": sid, "name": store["name"], "address": store.get("address", ""),
            "menu_url": store.get("menu_url", ""), "distance_mi": store_distance(config, store),
        }
        old = prev_stores.get(sid, {})
        if result and result.get("offers"):
            offers = history.annotate(result["offers"], seen, now)
            for offer in offers:
                offer["url"] = offer.get("url") or store.get("menu_url", "")
            info.update(status="ok", message="", scraped_at=now, platforms=result.get("platforms", []))
        else:
            offers = prev_products.get(sid, [])
            problem = (result or {}).get("error") or ("no products found" if result else "")
            if result is None:
                info.update({k: old.get(k) for k in ("status", "message", "scraped_at", "platforms")})
            elif offers:
                info.update(status="stale", message=f"{problem}; showing last good data",
                            scraped_at=old.get("scraped_at"), platforms=old.get("platforms", []))
            else:
                info.update(status="error", message=problem, scraped_at=None, platforms=[])
        info["product_count"] = len(offers)
        stores_out.append(info)
        products_out.extend(offers)

    history.save(history_path, seen, now)
    menu = {"generated_at": now, "origin": config.get("origin", {}), "stores": stores_out, "products": products_out}
    write_json_atomic(os.path.join(data_dir, "menu.json"), menu)
    return menu


def write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)
