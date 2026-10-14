"""Serve the website locally (and optionally to your phone on the same Wi-Fi)."""

import functools
import socket
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import SITE_DIR


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def run(port=8765, lan=False, open_browser=True):
    host = "0.0.0.0" if lan else "127.0.0.1"
    server = ThreadingHTTPServer((host, port), functools.partial(Handler, directory=str(SITE_DIR)))
    url = f"http://localhost:{port}/"
    print(f"Deals site running at {url}")
    if lan and lan_ip():
        print(f"On your phone (same Wi-Fi): http://{lan_ip()}:{port}/")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
