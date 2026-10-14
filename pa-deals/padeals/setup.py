"""Interactive helper that finds each store's menu link for you.

It opens a visible browser at the store's website. You click through to the online menu
(answering any age prompts), scroll a little, and close the window. The tool watches what
loads, works out which page held the products, and saves that link to stores.json.
"""

import re
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError

from .capture import Browser, Recorder, capture_menu
from .config import load_config, save_config, select_stores
from .parsers import extract_offers


def _ask(prompt, default="y"):
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return default == "y"
    return (answer or default).startswith("y")


def _watch_browsing(start_url):
    """Open a visible browser and wait until the user closes it. Returns (best_url, captures)."""
    sightings = {}
    last_urls = []

    def on_products(page_url, count):
        if page_url:
            sightings[page_url] = sightings.get(page_url, 0) + count

    with Browser(headless=False) as browser:
        context = browser.new_context()
        recorder = Recorder(context, on_products=on_products)

        def track(page):
            page.on("framenavigated", lambda frame: frame == page.main_frame and last_urls.append(frame.url))

        context.on("page", track)
        page = context.new_page()
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightError as exc:
            print(f"  (couldn't open {start_url}: {exc.message.splitlines()[0]}) - type the address yourself")
        while True:
            pages = [p for p in context.pages if not p.is_closed()]
            if not pages:
                break
            try:
                pages[-1].wait_for_timeout(500)
            except PlaywrightError:
                if not browser.browser.is_connected():
                    break
        best = max(sightings, key=sightings.get) if sightings else (last_urls[-1] if last_urls else "")
        return best, recorder.captures


def configure_store(config, store):
    print(f"\n=== {store['name']} - {store.get('address', '')}")
    start = store.get("menu_url") or store.get("website") or \
        "https://www.google.com/search?q=" + quote_plus(f"{store['name']} {store.get('address', '')} menu")
    print("  A browser window will open. In it:")
    print("    1. Go to this store's online MEDICAL menu (the page listing products with prices).")
    print("    2. Answer any age/patient prompts and scroll down a bit so products load.")
    print("    3. Close the browser window when you're done.")
    if not _ask("  Ready? [Y/n] "):
        return False
    url, captures = _watch_browsing(start)
    offers, platforms = extract_offers(store["id"], captures)
    if not url:
        print("  Didn't see a menu page. Skipping this store for now.")
        return False
    print(f"  Menu page: {url}")
    if offers:
        print(f"  Saw {len(offers)} prices ({', '.join(platforms)}). Example: "
              f"{offers[0]['name']} {offers[0]['size']} ${offers[0]['price']:.2f}")
    else:
        print("  Didn't recognize any prices on that page. You can still save it and check the dump after scraping.")
    if not _ask("  Save this as the store's menu link? [Y/n] "):
        return False
    store["menu_url"] = url
    store["enabled"] = True
    store.pop("headed", None)
    save_config(config)

    print("  Checking that it also works with a hidden browser (how scheduled scans run)...")
    with Browser(headless=True) as browser:
        try:
            hidden_offers, _ = extract_offers(store["id"], capture_menu(browser, url, log=lambda m: None))
        except Exception:
            hidden_offers = []
    if hidden_offers:
        print(f"  OK: {len(hidden_offers)} prices found automatically.")
    else:
        store["headed"] = True
        save_config(config)
        print("  Hidden browser saw nothing, so this store will use a visible browser window when scanning.")
    return True


def add_store(config):
    print("\nAdd a dispensary. Press Enter to skip optional fields.")
    name = input("  Name: ").strip()
    if not name:
        return None
    base_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "store"
    taken = {s["id"] for s in config["stores"]}
    store_id, n = base_id, 2
    while store_id in taken:
        store_id, n = f"{base_id}-{n}", n + 1
    store = {"id": store_id, "name": name, "address": input("  Address: ").strip(),
             "website": input("  Website (optional): ").strip(), "menu_url": "", "enabled": False}
    print("  Coordinates let the site show distance. In Google Maps, right-click the store to copy them.")
    lat_lng = input("  Latitude, longitude (optional, e.g. 40.58, -79.56): ").strip()
    try:
        lat, lng = (float(x) for x in lat_lng.split(",", 1))
        store.update(lat=lat, lng=lng)
    except ValueError:
        if lat_lng:
            print("  Couldn't read those coordinates; you can add lat/lng in stores.json later.")
    config["stores"].append(store)
    save_config(config)
    return store


def run(store_ids=None, add=False, redo=False):
    config = load_config()
    if add:
        store = add_store(config)
        targets = [store] if store else []
    else:
        targets = select_stores(config, store_ids, only_ready=False)
        if not store_ids and not redo:
            targets = [s for s in targets if not s.get("menu_url")]
    if not targets:
        print("Every store already has a menu link. Use --store ID to redo one, or --add for a new store.")
        return
    for store in targets:
        configure_store(config, store)
    print("\nAll set. Now run:  python -m padeals scrape")
