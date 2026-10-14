# PA Dispensary Deals

A personal tool that scans the online menus of medical dispensaries near Apollo, PA
(15613) and shows them on one local website:

- **Deals**: everything on sale or recently cut in price, biggest discount first
- **Cheapest**: best price per gram, by category
- **New**: products that just showed up (or came back in stock) since the last scan
- **Watchlist**: strains you care about, and which stores have them right now
- **Search** any strain or brand across every store (tolerates small typos)

It runs on your own computer. Each scan opens the stores' menu pages in a hidden
browser, the way you would, so it sees the same medical prices you'd see.

## Status: what's been tested

| Part | Tested? |
|---|---|
| Reading Dutchie, Jane, and Dutchie Plus/Sweed-style menu data | Yes, with sample data shaped like each platform |
| Clicking past age gates, menus inside iframes, paging through the full menu | Yes, a real browser against a fake dispensary site |
| New-item / price-drop / back-in-stock tracking, website | Yes |
| **The real dispensary websites** | **No.** They were blocked from the cloud machine this was built on |

So the first real scan may hit a store whose menu needs a tweak. The tool is built to
tell you when that happens, and the section **When a store shows 0 prices** below covers
what to do.

## One-time setup (about 10 minutes)

You need **Python 3.10 or newer**.
- Windows: install from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** in the installer.
- Mac: install from python.org, or `brew install python`.

**1. Get the code**

```
git clone https://github.com/Skillerpwns/Fun.git
cd Fun
git checkout claude/gifted-archimedes-2o36n6
cd pa-deals
```

(Once this branch is merged you can skip the `git checkout` line.)

**2. Install** (run these inside the `pa-deals` folder)

Windows (Command Prompt or PowerShell):
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Mac / Linux:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Every time you open a new terminal, run the `activate` line again before using the tool.
When it's active your prompt starts with `(.venv)`. If you see `command not found: python`,
it isn't active yet (a Mac only has `python3` until you activate it).

**3. Point it at each store's menu**

```
python -m padeals setup
```

For each store, a browser window opens on the store's website. Click through to the
**online medical menu** (the page that lists products with prices), answer any age or
patient prompts, scroll a little, then **close the window**. The tool works out which page
had the products, saves it to `stores.json`, and checks that a hidden browser can read it.
Type `n` at "Ready?" to skip a store.

**4. Scan and open the site**

```
python -m padeals scrape
python -m padeals serve
```

`scrape` takes about 15 seconds per store. `serve` opens http://localhost:8765 in your browser.

## Everyday use

- Double-click **`update.bat`** (Windows) or run **`./update.sh`** (Mac/Linux). It scans, then opens the site.
- To use the site on your phone, run `python -m padeals serve --lan` and open the address
  it prints on your phone (both devices on the same Wi-Fi).
- To refresh automatically, schedule `python -m padeals scrape` a few times a day:
  - **Windows**: Task Scheduler → Create Basic Task → Daily, repeat every 4 hours →
    Action "Start a program": `C:\path\to\Fun\pa-deals\.venv\Scripts\python.exe`,
    arguments `-m padeals scrape`, "Start in": `C:\path\to\Fun\pa-deals`.
  - **Mac/Linux**: `crontab -e`, then add
    `0 8,12,16,20 * * * cd /path/to/Fun/pa-deals && .venv/bin/python -m padeals scrape`

Your watchlist and filters are saved in your browser.

## The stores

The starting list in `stores.json` has these stores. I found them in news coverage
(2018–2022), Cresco's store list and directory sites, so one may have closed or been
renamed, and newer stores may be missing. Distances are straight-line from Apollo, using
approximate coordinates.

| Store | Approx. distance | Note |
|---|---|---|
| Zen Leaf, New Kensington | 10 mi | |
| Sunnyside, New Kensington | 10 mi | Cresco Labs, formerly CY+ |
| RISE, Monroeville | 15 mi | |
| The Healing Center, Monroeville | 16 mi | Only found 2018 plans. Check that it's open |
| Solevo Wellness, Greensburg | 19 mi | |
| Maitri Medicinals, Greensburg | 20 mi | |
| Ayr Wellness, Richland (Gibsonia) | 21 mi | |
| Curaleaf, Greensburg | 21 mi | |
| Ayr Wellness, Indiana | 23 mi | |
| Sunnyside, Butler | 26 mi | |

- **Add a store:** `python -m padeals setup --add`
- **Redo a store's link:** `python -m padeals setup --store zen-leaf-new-kensington`
- **Stop scanning a store:** set `"enabled": false` for it in `stores.json`
- **List stores and their status:** `python -m padeals stores`
- To check for stores I missed, search Leafly or Weedmaps for dispensaries near 15613.

## When a store shows 0 prices

The site's **Stores** panel shows a red dot and the reason. Try these in order:

1. **Bot check:** `python -m padeals scrape --store STORE-ID --headed` runs that store
   with a visible browser. If that works, add `"headed": true` to the store in `stores.json`.
   (`setup` already does this when it notices the hidden browser failing.)
2. **Wrong page:** run `python -m padeals setup --store STORE-ID` and pick the actual menu
   page, not the store's homepage.
3. **New menu format:** every failed scan saves what the page loaded to
   `dumps/STORE-ID.json`. Open Claude Code in this `pa-deals` folder and say something
   like *"Sunnyside New Kensington shows no prices. Look at dumps/sunnyside-new-kensington.json
   and fix the parser."* Claude Code can run the scraper on your machine and fix it there.

## Continuing with Claude Code on your computer

This folder is self-contained. Open a terminal in `pa-deals`, run `claude`, and ask for
what you want next. Some ideas:
- Text or email alerts when a watchlist strain appears or drops below a price
- Store-wide specials (like "20% off flower Tuesdays") that don't show up as product prices
- Price history charts

The section **How it works** below is the map for that.

## How it works

```
stores.json            which stores to scan, and your home location
padeals/
  capture.py           opens a menu in a browser and records every JSON response it loads
  paginate.py          re-sends the products request without category filters, page by page
  parsers/             recognizes product data in those responses:
    dutchie.py           Dutchie menus (dutchie.com and embedded Dutchie menus)
    jane.py              Jane menus (iheartjane, served from Algolia)
    variants.py          Dutchie Plus, Sweed, and other "product with size variants" menus
    generic.py           fallback for unknown menus: any list of things with names and prices
  normalize.py         category, size in grams, THC %, price per gram
  history.py           first-seen dates and past prices, used for NEW and price-drop badges
  menu.py              merges a scan into site/data/menu.json, keeping a failed store's last good data
  setup.py             the interactive menu-link finder
site/                  the website (plain HTML/JS, no build step), reads data/menu.json
tests/                 run with: python -m unittest
```

Recording the page's own data, instead of calling each platform's private API directly,
means the scan keeps working when a platform changes its API addresses or request formats.

## Tests

```
python -m unittest
```

The browser tests start a small fake dispensary site on your computer and need Playwright
installed (step 2 above).

## Notes

- Pennsylvania is still medical-only, so these are medical menus and prices.
- This reads public menu pages for personal use. Keep scans to a few times a day, like
  checking the menus yourself. Dispensary and menu-platform terms of service generally
  don't welcome automated access, so don't turn this into a public site without asking them.
- Prices can change between a scan and your visit. Check the store's menu (each result
  links to it) before you drive over.
