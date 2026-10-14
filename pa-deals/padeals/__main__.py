"""Command line: python -m padeals {setup,scrape,serve,stores}"""

import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m padeals", description="PA dispensary deal finder")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="find and save each store's menu link (opens a browser)")
    p.add_argument("--store", action="append", help="only this store id (repeatable)")
    p.add_argument("--add", action="store_true", help="add a new dispensary")
    p.add_argument("--redo", action="store_true", help="also redo stores that already have a link")

    p = sub.add_parser("scrape", help="scan the menus and update the site's data")
    p.add_argument("--store", action="append", help="only this store id (repeatable)")
    p.add_argument("--headed", action="store_true", help="show the browser (helps with bot checks)")
    p.add_argument("--dump", action="store_true", help="save raw menu data to dumps/ for debugging")

    p = sub.add_parser("serve", help="open the deals website")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--lan", action="store_true", help="also allow phones on your Wi-Fi to open it")
    p.add_argument("--no-open", action="store_true", help="don't open a browser tab")

    sub.add_parser("stores", help="list configured stores")

    args = parser.parse_args(argv)
    if args.command == "setup":
        from . import setup
        setup.run(args.store, add=args.add, redo=args.redo)
    elif args.command == "scrape":
        from . import scrape
        from .config import load_config
        scrape.run(load_config(), args.store, headed=args.headed, dump=args.dump)
    elif args.command == "serve":
        from . import serve
        serve.run(port=args.port, lan=args.lan, open_browser=not args.no_open)
    elif args.command == "stores":
        from .config import load_config, store_distance
        config = load_config()
        for s in sorted(config["stores"], key=lambda s: store_distance(config, s) or 999):
            ready = "ready" if s.get("enabled") and s.get("menu_url") else "needs setup"
            print(f"{s['id']:28} {store_distance(config, s) or '?':>5} mi  {ready:12} {s['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
