"""Scrape every configured store and write site/data/menu.json."""

import json
import os
import time

from .capture import Browser, capture_menu
from .config import DATA_DIR, DUMP_DIR, select_stores
from .history import now_iso
from .menu import build
from .parsers import extract_offers


def dump_captures(store_id, captures):
    os.makedirs(DUMP_DIR, exist_ok=True)
    path = DUMP_DIR / f"{store_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"url": c["url"], "method": c["method"], "post_data": c.get("post_data"), "json": c["json"]}
                   for c in captures], f, indent=1)
    return path


def scrape_store(browser, store, dump=False, log=print):
    if not store.get("menu_url"):
        log("    skipped: no menu link yet. Run `python -m padeals setup --store " + store["id"] + "`")
        return {"offers": [], "platforms": [], "error": "no menu link yet"}
    started = time.time()
    try:
        captures = capture_menu(browser, store["menu_url"], log)
    except Exception as exc:
        log(f"    FAILED: {exc}")
        return {"offers": [], "platforms": [], "error": f"page failed to load: {str(exc).splitlines()[0][:160]}"}
    offers, platforms = extract_offers(store["id"], captures)
    if dump or not offers:
        log(f"    saved {len(captures)} raw responses to {dump_captures(store['id'], captures)}")
    if offers:
        log(f"    {len(offers)} prices found via {', '.join(platforms)} in {time.time() - started:.0f}s")
        return {"offers": offers, "platforms": platforms, "error": ""}
    log("    no products found. Try again with --headed, or open the dump file above to see what loaded.")
    return {"offers": [], "platforms": [], "error": "no products found on the menu page"}


def run(config, store_ids=None, headed=False, dump=False, log=print):
    stores = select_stores(config, store_ids)
    if not stores:
        raise SystemExit("No stores are ready to scan. Run `python -m padeals setup` first to add menu links.")
    results = {}
    # Stores marked "headed" in stores.json need a visible browser to get past bot checks.
    groups = [(False, [s for s in stores if not (headed or s.get("headed"))]),
              (True, [s for s in stores if headed or s.get("headed")])]
    count = 0
    for visible, group in groups:
        if not group:
            continue
        with Browser(headless=not visible) as browser:
            for store in group:
                count += 1
                log(f"[{count}/{len(stores)}] {store['name']}")
                results[store["id"]] = scrape_store(browser, store, dump=dump, log=log)
    menu = build(config, results, now_iso(), data_dir=DATA_DIR)
    ok = sum(1 for r in results.values() if r["offers"])
    log(f"\nDone: {ok}/{len(results)} stores scanned, {len(menu['products'])} prices in site/data/menu.json")
    return menu
