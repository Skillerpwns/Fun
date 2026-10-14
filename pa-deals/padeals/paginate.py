"""Fetch the whole menu by replaying the request that returned the first page of products.

A menu page usually loads only one category or one page of products. We find the captured
request that returned products, then re-send it from the same browser session (same
cookies) with category filters removed and the page number stepped forward.

Two request shapes are handled:
  * Algolia search (Jane menus): {"requests": [{"indexName", "params"}]} bodies.
  * Everything else with JSON variables: GraphQL (Dutchie, Dutchie Plus) or JSON POST
    bodies (Sweed and others) containing page/perPage or offset/limit fields.
"""

import copy
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .parsers import count_products

MAX_PAGES = 60
BIG_PAGE = 100
ALGOLIA_PAGE = 500

DROP_HEADERS = {"host", "content-length", "accept-encoding", "connection", "cookie"}
PAGE_KEYS = ("page", "pageNumber", "currentPage", "pageIndex")
OFFSET_KEYS = ("offset", "skip", "from")
SIZE_KEYS = ("perPage", "pageSize", "limit", "size", "per_page", "page_size", "first", "take", "hitsPerPage")
# Category/brand/search filters that narrow the menu to what the page happened to show.
FILTER_KEYS = {"types", "subcategories", "strainTypes", "category", "categories", "kind", "kinds",
               "subcategory", "productTypes", "brandIds", "brands", "search", "searchQuery", "query"}


def expand(context, captures, log=print):
    # One replay per distinct request, starting from the response that held the most products
    # (a "staff picks" carousel and the main grid can share the same endpoint).
    best = {}
    for capture in captures:
        if capture["method"] == "EMBEDDED":
            continue
        products = count_products(capture["json"])
        if products:
            signature = _signature(capture)
            if signature not in best or products > best[signature][0]:
                best[signature] = (products, capture)
    extra = []
    for _, capture in best.values():
        try:
            pages = _expand_one(context, capture)
        except Exception as exc:  # one odd request shouldn't sink the whole store
            log(f"    could not page through {urlsplit(capture['url']).netloc}: {exc}")
            pages = []
        if pages:
            log(f"    fetched {len(pages)} extra page(s) from {urlsplit(capture['url']).netloc}")
        extra.extend({"url": capture["url"], "method": "REPLAY", "headers": {}, "post_data": None, "json": doc}
                     for doc in pages)
    return extra


def _signature(capture):
    parts = urlsplit(capture["url"])
    query = dict(parse_qsl(parts.query))
    body = _json_or_none(capture.get("post_data"))
    operation = query.get("operationName") or (body.get("operationName") if isinstance(body, dict) else "")
    index = ""
    if isinstance(body, dict) and isinstance(body.get("requests"), list):
        index = ",".join(str(r.get("indexName")) for r in body["requests"] if isinstance(r, dict))
    return (capture["method"], parts.netloc, parts.path, operation, index)


def _json_or_none(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _headers(capture):
    return {k: v for k, v in capture["headers"].items()
            if k.lower() not in DROP_HEADERS and not k.startswith(":")}


def _send(context, capture, url, body):
    data = json.dumps(body) if body is not None else None
    response = context.request.fetch(url, method=capture["method"], headers=_headers(capture), data=data,
                                     timeout=30000, fail_on_status_code=False)
    if not response.ok:
        return None
    try:
        return response.json()
    except Exception:
        return None


def _expand_one(context, capture):
    body = _json_or_none(capture.get("post_data"))
    if isinstance(body, dict) and _is_algolia(body):
        return _algolia_pages(context, capture, body)
    return _variable_pages(context, capture, body)


# ---------------------------------------------------------------- Algolia (Jane)

def _is_algolia(body):
    requests = body.get("requests")
    if isinstance(requests, list):
        return any(isinstance(r, dict) and "indexName" in r for r in requests)
    return isinstance(body.get("params"), str)


def _keep_store_filters(value):
    """facetFilters like [["store_id:12"], ["kind:flower"]] -> [["store_id:12"]].

    In a params string the list arrives JSON-encoded, and comes back the same way."""
    if isinstance(value, str) and value.lstrip().startswith("["):
        parsed = _json_or_none(value)
        return value if parsed is None else json.dumps(_keep_store_filters(parsed))
    if isinstance(value, list):
        kept = [_keep_store_filters(v) for v in value]
        return [v for v in kept if v not in ("", [], None)]
    return value if "store" in str(value) else ""


def _store_clause(filters):
    match = re.search(r"store_id\s*[:=]\s*\d+", filters or "")
    return match.group() if match else filters


def _algolia_request(request, page):
    request = dict(request)
    if isinstance(request.get("params"), str):
        pairs = []
        for key, value in parse_qsl(request["params"], keep_blank_values=True):
            if key in ("page", "hitsPerPage", "query"):
                continue
            if key == "facetFilters":
                value = _keep_store_filters(value)
            elif key == "filters":
                value = _store_clause(value)
            pairs.append((key, value))
        pairs += [("query", ""), ("page", str(page)), ("hitsPerPage", str(ALGOLIA_PAGE))]
        request["params"] = urlencode(pairs)
    else:
        if "facetFilters" in request:
            request["facetFilters"] = _keep_store_filters(request["facetFilters"])
        if "filters" in request:
            request["filters"] = _store_clause(request["filters"])
        request.update(query="", page=page, hitsPerPage=ALGOLIA_PAGE)
    return request


def _algolia_pages(context, capture, body):
    docs = []
    for page in range(MAX_PAGES):
        if isinstance(body.get("requests"), list):
            new_body = dict(body, requests=[_algolia_request(r, page) for r in body["requests"]])
        else:
            new_body = _algolia_request(body, page)
        doc = _send(context, capture, capture["url"], new_body)
        if not doc or not count_products(doc):
            break
        docs.append(doc)
        results = doc.get("results") if isinstance(doc.get("results"), list) else [doc]
        if all(r.get("page", 0) + 1 >= r.get("nbPages", 0) for r in results if isinstance(r, dict)):
            break
    return docs


# ------------------------------------------------- GraphQL / JSON variable pagination

def _locate_variables(capture, body):
    """Return (variables, rebuild) where rebuild(new_variables) -> (url, body) to send."""
    parts = urlsplit(capture["url"])
    query = parse_qsl(parts.query, keep_blank_values=True)
    query_vars = dict(query).get("variables")
    if capture["method"] == "GET" and query_vars:
        variables = _json_or_none(query_vars)
        if not isinstance(variables, dict):
            return None, None

        def rebuild(new_vars):
            pairs = [(k, json.dumps(new_vars, separators=(",", ":")) if k == "variables" else v) for k, v in query]
            return urlunsplit(parts._replace(query=urlencode(pairs))), None
        return variables, rebuild
    if isinstance(body, dict) and isinstance(body.get("variables"), dict):
        return body["variables"], lambda new_vars: (capture["url"], dict(body, variables=new_vars))
    if isinstance(body, dict):
        return body, lambda new_body: (capture["url"], new_body)
    return None, None


def _find_paging(node, path=()):
    """Find the dict holding a page or offset field. Returns (path, mode, key, size_key)."""
    if not isinstance(node, dict):
        return None
    size_key = next((k for k in SIZE_KEYS if _is_int(node.get(k))), None)
    for key in PAGE_KEYS:
        if _is_int(node.get(key)):
            return path, "page", key, size_key
    for key in OFFSET_KEYS:
        if _is_int(node.get(key)) and size_key:
            return path, "offset", key, size_key
    for key, value in node.items():
        found = _find_paging(value, path + (key,))
        if found:
            return found
    return None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _clear_filters(node):
    if isinstance(node, dict):
        for key in list(node):
            value = node[key]
            if key in FILTER_KEYS and isinstance(value, list):
                node[key] = []
            elif key in FILTER_KEYS and isinstance(value, str):
                del node[key]
            else:
                _clear_filters(value)
    elif isinstance(node, list):
        for value in node:
            _clear_filters(value)


def _variable_pages(context, capture, body):
    variables, rebuild = _locate_variables(capture, body)
    if variables is None:
        return []
    paging = _find_paging(variables)
    if not paging:
        return []
    path, mode, key, size_key = paging
    container = variables
    for step in path:
        container = container[step]
    original_size = container.get(size_key) if size_key else None
    first = container[key]
    start = 0 if mode == "offset" or first == 0 else 1

    # Widest first: all categories with big pages, then fall back to what the site used.
    attempts = [(True, max(original_size or 0, BIG_PAGE) if size_key else None),
                (True, original_size), (False, original_size)]
    tried = set()
    for clear, size in attempts:
        if (clear, size) in tried:
            continue
        tried.add((clear, size))
        docs = _run_pages(context, capture, variables, rebuild, path, mode, key, size_key, size, start, clear)
        if docs:
            return docs
    return []


def _run_pages(context, capture, variables, rebuild, path, mode, key, size_key, size, start, clear):
    docs, seen = [], set()
    for i in range(MAX_PAGES):
        new_vars = copy.deepcopy(variables)
        if clear:
            _clear_filters(new_vars)
        container = new_vars
        for step in path:
            container = container[step]
        if size_key and size:
            container[size_key] = size
        container[key] = start + i if mode == "page" else start + i * (size or container.get(size_key) or 0)
        url, new_body = rebuild(new_vars)
        doc = _send(context, capture, url, new_body)
        if not doc or not count_products(doc):
            break
        digest = hashlib.sha1(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        if digest in seen:  # the API ignored our page number; stop instead of looping
            break
        seen.add(digest)
        docs.append(doc)
    return docs
