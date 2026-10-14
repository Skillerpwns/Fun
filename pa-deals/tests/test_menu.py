import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from padeals.menu import build
from padeals.normalize import make_offer

CONFIG = {
    "origin": {"label": "Apollo", "lat": 40.5815, "lng": -79.5664},
    "stores": [
        {"id": "a", "name": "Store A", "lat": 40.59, "lng": -79.75, "menu_url": "https://a.test/menu", "enabled": True},
        {"id": "b", "name": "Store B", "lat": 40.30, "lng": -79.54, "menu_url": "https://b.test/menu", "enabled": True},
    ],
}


def offer(store, name, price, sale=None):
    return make_offer(store_id=store, source="t", name=name, category_hints=("Flower",), size_label="3.5g",
                      price=price, sale_price=sale)


def at(days=0, hours=0):
    base = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    return (base + timedelta(days=days, hours=hours)).isoformat()


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def run_scrape(self, when, results):
        return build(CONFIG, results, when, data_dir=self.dir)

    def products(self, menu, store):
        return {p["name"]: p for p in menu["products"] if p["store_id"] == store}

    def test_first_scrape_is_baseline_then_new_items_are_flagged(self):
        menu = self.run_scrape(at(0), {"a": {"offers": [offer("a", "GMO", 40)], "platforms": ["t"]}})
        self.assertFalse(self.products(menu, "a")["GMO"]["is_new"])

        menu = self.run_scrape(at(0, 6), {"a": {"offers": [offer("a", "GMO", 40), offer("a", "Runtz", 45)],
                                                "platforms": ["t"]}})
        a = self.products(menu, "a")
        self.assertFalse(a["GMO"]["is_new"])
        self.assertTrue(a["Runtz"]["is_new"])

        menu = self.run_scrape(at(4), {"a": {"offers": [offer("a", "Runtz", 45)], "platforms": ["t"]}})
        self.assertFalse(self.products(menu, "a")["Runtz"]["is_new"])  # NEW badge expires after 48h

    def test_price_drop_is_reported_for_a_week(self):
        self.run_scrape(at(0), {"a": {"offers": [offer("a", "GMO", 50)], "platforms": ["t"]}})
        menu = self.run_scrape(at(1), {"a": {"offers": [offer("a", "GMO", 40)], "platforms": ["t"]}})
        self.assertEqual(self.products(menu, "a")["GMO"]["price_drop_from"], 50)
        menu = self.run_scrape(at(9), {"a": {"offers": [offer("a", "GMO", 40)], "platforms": ["t"]}})
        self.assertIsNone(self.products(menu, "a")["GMO"]["price_drop_from"])

    def test_back_in_stock(self):
        self.run_scrape(at(0), {"a": {"offers": [offer("a", "GMO", 50)], "platforms": ["t"]}})
        self.run_scrape(at(1), {"a": {"offers": [offer("a", "Runtz", 50)], "platforms": ["t"]}})
        menu = self.run_scrape(at(6), {"a": {"offers": [offer("a", "GMO", 50)], "platforms": ["t"]}})
        self.assertTrue(self.products(menu, "a")["GMO"]["back_in_stock"])

    def test_failed_store_keeps_last_good_data(self):
        self.run_scrape(at(0), {"a": {"offers": [offer("a", "GMO", 40)], "platforms": ["t"]},
                                "b": {"offers": [offer("b", "Runtz", 45)], "platforms": ["t"]}})
        menu = self.run_scrape(at(1), {"a": {"offers": [], "platforms": [], "error": "page failed to load"}})
        stores = {s["id"]: s for s in menu["stores"]}
        self.assertEqual(stores["a"]["status"], "stale")
        self.assertIn("page failed to load", stores["a"]["message"])
        self.assertEqual(stores["b"]["status"], "ok")  # not scraped this run, left as it was
        self.assertIn("GMO", self.products(menu, "a"))
        self.assertIn("Runtz", self.products(menu, "b"))

    def test_store_distance_and_links(self):
        menu = self.run_scrape(at(0), {"a": {"offers": [offer("a", "GMO", 40)], "platforms": ["t"]}})
        store = menu["stores"][0]
        self.assertAlmostEqual(store["distance_mi"], 9.6, delta=0.3)
        self.assertEqual(menu["products"][0]["url"], "https://a.test/menu")


if __name__ == "__main__":
    unittest.main()
