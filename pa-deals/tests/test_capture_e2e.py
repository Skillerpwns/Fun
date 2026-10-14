"""End-to-end: a real headless browser against the fake menus in mock_menu_server.py."""

import unittest

try:
    from padeals import setup
    from padeals.capture import Browser, capture_menu
except ImportError:  # Playwright not installed
    Browser = None

from padeals.parsers import extract_offers

from . import mock_menu_server

DUTCHIE_OFFERS = 12 * 2 + 45   # 12 flower products x 2 sizes + 45 single-size products
JANE_OFFERS = 9 * 2 + 34       # store 7 only: 9 flower x 2 sizes + 34 single-size


@unittest.skipIf(Browser is None, "playwright is not installed")
class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = mock_menu_server.start()
        cls.browser = Browser(headless=True).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.browser.__exit__(None, None, None)
        cls.server.shutdown()
        cls.server.server_close()

    def scrape(self, path):
        captures = capture_menu(self.browser, self.base + path, log=lambda m: None)
        return extract_offers("test", captures)

    def test_dutchie_age_gate_and_full_menu(self):
        offers, platforms = self.scrape("/dutchie")
        self.assertEqual(platforms, ["dutchie"])
        self.assertEqual(len(offers), DUTCHIE_OFFERS)  # page showed 10 flower items; we got everything
        self.assertEqual({o["category"] for o in offers}, {"flower", "vape", "concentrate", "preroll", "tincture"})

    def test_dutchie_inside_iframe(self):
        offers, _ = self.scrape("/embedded")
        self.assertEqual(len(offers), DUTCHIE_OFFERS)

    def test_jane_algolia_full_menu_for_one_store(self):
        offers, platforms = self.scrape("/jane")
        self.assertEqual(platforms, ["jane"])
        self.assertEqual(len(offers), JANE_OFFERS)



@unittest.skipIf(Browser is None, "playwright is not installed")
class SetupTests(unittest.TestCase):
    # Separate class: Playwright allows one running instance per thread, and setup starts its own.
    def setUp(self):
        self.server, self.base = mock_menu_server.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_setup_finds_the_menu_page_the_user_browsed_to(self):
        class HiddenBrowser(Browser):
            """Headless, and closes the page once the menu data arrives, like a person would."""
            def __init__(self, headless=True):
                super().__init__(headless=True)

            def new_context(self):
                context = super().new_context()
                # "requestfinished" fires after the recorder has read the response body.
                context.on("requestfinished", lambda r: "graphql" in r.url and r.frame.page.close())
                return context

        original = setup.Browser
        setup.Browser = HiddenBrowser
        try:
            url, captures = setup._watch_browsing(self.base + "/autoload")
        finally:
            setup.Browser = original
        self.assertEqual(url, self.base + "/autoload")
        offers, _ = extract_offers("test", captures)
        self.assertEqual(len(offers), 6)  # 5 products, the flower one has two sizes


if __name__ == "__main__":
    unittest.main()
