"""A tiny fake dispensary site for end-to-end tests of the browser capture.

/dutchie        age gate, then loads one page of Flower from a Dutchie-style GraphQL GET
/embedded       a dispensary homepage with /dutchie inside an iframe
/jane           loads one page of flower from an Algolia-style POST, like Jane menus
/autoload       loads a few products right away (for testing `setup`)

The APIs honor page / perPage / category filters so the tests can check that we fetch
the whole menu, not just what the page first showed.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from . import fakes

DUTCHIE = fakes.dutchie_catalog(57)
JANE = fakes.jane_catalog(43, store_id=7) + fakes.jane_catalog(6, store_id=8)

DUTCHIE_PAGE = """<!doctype html><html><body>
<div id="gate"><p>Are you 21 or a registered patient?</p><button id="yes">Yes, I am 21+</button></div>
<ul id="menu"></ul>
<script>
document.getElementById('yes').onclick = async () => {
  document.cookie = 'session=ok; path=/';
  document.getElementById('gate').remove();
  const variables = {includeEnterpriseSpecials: false, productsFilter: {dispensaryId: 'abc', pricingType: 'med',
    strainTypes: [], subcategories: [], types: ['Flower'], Status: 'Active'}, page: 0, perPage: 10};
  const extensions = {persistedQuery: {version: 1, sha256Hash: 'deadbeef'}};
  const url = '/graphql?operationName=FilteredProducts&variables=' + encodeURIComponent(JSON.stringify(variables)) +
    '&extensions=' + encodeURIComponent(JSON.stringify(extensions));
  const data = await (await fetch(url, {headers: {'apollographql-client-name': 'Marketplace (production)'}})).json();
  for (const p of data.data.filteredProducts.products) {
    const li = document.createElement('li'); li.textContent = p.Name; document.getElementById('menu').append(li);
  }
};
</script></body></html>"""

# A page that loads a few products right away, for testing `setup`.
AUTOLOAD_PAGE = """<!doctype html><html><body><script>
(async () => {
  document.cookie = 'session=ok; path=/';
  const variables = {productsFilter: {dispensaryId: 'abc', types: []}, page: 0, perPage: 5};
  await fetch('/graphql?operationName=FilteredProducts&variables=' + encodeURIComponent(JSON.stringify(variables)));
})();
</script></body></html>"""

EMBEDDED_PAGE = """<!doctype html><html><body><h1>Some Dispensary</h1>
<iframe src="/dutchie" width="900" height="700"></iframe></body></html>"""

JANE_PAGE = """<!doctype html><html><body><ul id="menu"></ul>
<script>
(async () => {
  const params = 'query=&hitsPerPage=12&page=0&facetFilters=' +
    encodeURIComponent(JSON.stringify([['store_id:7'], ['kind:flower']]));
  const res = await fetch('/1/indexes/*/queries?x-algolia-api-key=public&x-algolia-application-id=TEST', {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({requests: [{indexName: 'menu-products-production', params}]})});
  const data = await res.json();
  for (const h of data.results[0].hits) {
    const li = document.createElement('li'); li.textContent = h.name; document.getElementById('menu').append(li);
  }
})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    requests_seen = []

    def log_message(self, *args):
        pass

    def _send(self, body, content_type="application/json", status=200):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        Handler.requests_seen.append(self.path)
        if url.path == "/dutchie":
            return self._send(DUTCHIE_PAGE, "text/html")
        if url.path == "/embedded":
            return self._send(EMBEDDED_PAGE, "text/html")
        if url.path == "/jane":
            return self._send(JANE_PAGE, "text/html")
        if url.path == "/autoload":
            return self._send(AUTOLOAD_PAGE, "text/html")
        if url.path == "/graphql":
            if "session=ok" not in (self.headers.get("Cookie") or ""):
                return self._send({"errors": [{"message": "no session"}]}, status=403)
            variables = json.loads(dict(parse_qsl(url.query))["variables"])
            types = variables["productsFilter"].get("types") or []
            products = [p for p in DUTCHIE if not types or p["type"] in types]
            per_page = min(variables.get("perPage", 10), 50)  # like real APIs, cap the page size
            start = variables.get("page", 0) * per_page
            return self._send(fakes.dutchie_response(products[start:start + per_page]))
        return self._send({"error": "not found"}, status=404)

    def do_POST(self):
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if url.path.startswith("/1/indexes/"):
            if dict(parse_qsl(url.query)).get("x-algolia-api-key") != "public":
                return self._send({"message": "Invalid API key"}, status=403)
            results = []
            for request in body["requests"]:
                params = dict(parse_qsl(request["params"]))
                facets = [f for group in json.loads(params.get("facetFilters") or "[]") for f in group]
                hits = JANE
                for facet in facets:
                    key, value = facet.split(":", 1)
                    hits = [h for h in hits if str(h.get(key)) == value]
                per_page, page = int(params.get("hitsPerPage", 20)), int(params.get("page", 0))
                pages = max(1, -(-len(hits) // per_page))
                results.append({"hits": hits[page * per_page:(page + 1) * per_page], "page": page,
                                "nbPages": pages, "hitsPerPage": per_page, "nbHits": len(hits)})
            return self._send({"results": results})
        return self._send({"error": "not found"}, status=404)


def start():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"
