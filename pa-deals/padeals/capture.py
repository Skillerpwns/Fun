"""Open a dispensary's menu in a real browser and record the product data it loads.

Rather than reverse-engineering each menu platform's private API (which changes often),
we let the page load normally and keep every JSON response it receives. Then
paginate.py replays the request that returned products to pull the rest of the menu.
"""

import json
import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from . import paginate
from .parsers import count_products

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# Age gates, "are you a patient?" prompts and cookie banners. Clicked if they show up.
_AGE_GATE = (r"yes\b.*|i am (over |at least )?(18|21).*|i'?m (over |at least )?(18|21).*|"
             r"i am a (registered |medical )?patient.*|enter( site)?")
GATE_BUTTONS = re.compile(
    rf"^\s*({_AGE_GATE}|medical( patient)?|continue|i agree|agree|accept( all)?( cookies)?|confirm)\s*$", re.I)
# Links only for age-gate wording: a link named "Medical" is often site navigation.
GATE_LINKS = re.compile(rf"^\s*({_AGE_GATE})\s*$", re.I)

EMBEDDED_STATE_JS = """() => {
  const out = [];
  const next = document.getElementById('__NEXT_DATA__');
  if (next) out.push(next.textContent);
  for (const key of ['__APOLLO_STATE__', '__INITIAL_STATE__', '__PRELOADED_STATE__']) {
    try { if (window[key]) out.push(JSON.stringify(window[key])); } catch (e) {}
  }
  return out;
}"""


class Recorder:
    """Keeps every JSON response a browser context receives."""

    def __init__(self, context, on_products=None):
        self.captures = []
        self.on_products = on_products
        context.on("response", self._on_response)

    def _on_response(self, response):
        try:
            if response.status >= 300:
                return
            request = response.request
            content_type = response.headers.get("content-type", "")
            url = response.url
            if "json" not in content_type and request.resource_type not in ("xhr", "fetch"):
                return
            data = response.json()
        except Exception:  # bodies of redirects, aborted requests, or non-JSON text
            return
        try:
            headers = request.all_headers()  # includes custom API headers the replay needs
        except Exception:
            headers = request.headers
        capture = {
            "url": url,
            "method": request.method,
            "headers": dict(headers),
            "post_data": request.post_data,
            "json": data,
        }
        self.captures.append(capture)
        if self.on_products:
            products = count_products(data)
            if products:
                try:
                    page_url = response.frame.page.url
                except Exception:
                    page_url = ""
                self.on_products(page_url, products)

    def add_embedded(self, page):
        """Some menus render server-side and ship the data inside the HTML instead of via XHR."""
        for frame in page.frames:
            try:
                blobs = frame.evaluate(EMBEDDED_STATE_JS)
            except PlaywrightError:
                continue
            for blob in blobs or []:
                try:
                    self.captures.append({"url": frame.url, "method": "EMBEDDED", "headers": {},
                                          "post_data": None, "json": json.loads(blob)})
                except (TypeError, ValueError):
                    pass


class Browser:
    def __init__(self, headless=True):
        self.headless = headless

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=self.headless, args=["--disable-blink-features=AutomationControlled"])
        return self

    def __exit__(self, *exc):
        try:
            self.browser.close()
        except PlaywrightError:
            pass  # already gone, e.g. the user closed the window
        finally:
            self._pw.stop()

    def new_context(self):
        return self.browser.new_context(
            user_agent=USER_AGENT, viewport={"width": 1366, "height": 900},
            locale="en-US", timezone_id="America/New_York")


def click_gates(page, rounds=2):
    for _ in range(rounds):
        clicked = False
        for frame in page.frames:
            for role, pattern in (("button", GATE_BUTTONS), ("link", GATE_LINKS)):
                try:
                    target = frame.get_by_role(role, name=pattern).first
                    if target.is_visible(timeout=300):
                        target.click(timeout=2000)
                        clicked = True
                        page.wait_for_timeout(1200)
                except PlaywrightError:
                    pass
        if not clicked:
            return


def scroll_everything(page, steps=10):
    for _ in range(steps):
        try:
            page.mouse.move(683, 500)
            page.mouse.wheel(0, 2500)
            for frame in page.frames:
                frame.evaluate("() => window.scrollBy(0, 2500)")
        except PlaywrightError:
            pass
        page.wait_for_timeout(700)


def capture_menu(browser, url, log=print):
    """Load one menu URL and return the list of captured JSON responses."""
    context = browser.new_context()
    recorder = Recorder(context)
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        click_gates(page)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightError:
            pass
        click_gates(page, rounds=1)
        scroll_everything(page)
        recorder.add_embedded(page)
        extra = paginate.expand(context, recorder.captures, log)
        return recorder.captures + extra
    finally:
        context.close()
