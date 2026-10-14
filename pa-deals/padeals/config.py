"""Paths and the stores.json file you edit to choose which dispensaries to scan."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORES_FILE = ROOT / "stores.json"
SITE_DIR = ROOT / "site"
DATA_DIR = SITE_DIR / "data"
DUMP_DIR = ROOT / "dumps"


def load_config():
    with open(STORES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(STORES_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def miles_between(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def store_distance(config, store):
    origin = config.get("origin", {})
    return miles_between(origin.get("lat"), origin.get("lng"), store.get("lat"), store.get("lng"))


def select_stores(config, ids=None, only_ready=True):
    stores = config["stores"]
    if ids:
        wanted = set(ids)
        unknown = wanted - {s["id"] for s in stores}
        if unknown:
            raise SystemExit(f"Unknown store id(s): {', '.join(sorted(unknown))}. See stores.json.")
        return [s for s in stores if s["id"] in wanted]
    if only_ready:
        return [s for s in stores if s.get("enabled") and s.get("menu_url")]
    return stores
