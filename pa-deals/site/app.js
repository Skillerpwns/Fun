"use strict";

const CATEGORY_LABELS = {
  flower: "Flower", preroll: "Pre-rolls", vape: "Vapes", concentrate: "Concentrates",
  edible: "Edibles", tincture: "Tinctures", capsule: "Capsules", topical: "Topicals", other: "Other",
};
const VIEW_SORT = { deals: "discount", cheapest: "ppg", new: "newest", watch: "price", all: "ppg" };
const PAGE = 150;

const saved = loadPrefs();
const state = {
  view: saved.view || "deals",
  category: saved.category || "all",
  sort: saved.sort || "auto",
  distance: saved.distance || "",
  strainType: saved.strainType || "",
  saleOnly: !!saved.saleOnly,
  hiddenStores: new Set(saved.hiddenStores || []),
  watch: saved.watch || [],
  query: "",
  shown: PAGE,
};
let menu = null;
let stores = {};

// ---------------------------------------------------------------- utilities

function loadPrefs() {
  try { return JSON.parse(localStorage.getItem("padeals-prefs") || "{}"); } catch (e) { return {}; }
}

function savePrefs() {
  const { view, category, sort, distance, strainType, saleOnly, watch } = state;
  try {
    localStorage.setItem("padeals-prefs", JSON.stringify({
      view, category, sort, distance, strainType, saleOnly, watch, hiddenStores: [...state.hiddenStores],
    }));
  } catch (e) { /* private mode: preferences just won't stick */ }
}

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "#";
}

function money(n) {
  return n == null ? "" : "$" + Number(n).toFixed(2);
}

function norm(text) {
  return String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function ago(iso) {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function withinOneEdit(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  if (a.length === b.length) {  // one swapped pair of neighbours counts as one typo ("strian")
    const diff = [...a].map((c, i) => (c === b[i] ? -1 : i)).filter((i) => i >= 0);
    if (diff.length === 2 && diff[1] === diff[0] + 1 && a[diff[0]] === b[diff[1]] && a[diff[1]] === b[diff[0]]) return true;
  }
  let i = 0, j = 0, edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i++; j++; continue; }
    if (++edits > 1) return false;
    if (a.length > b.length) i++;
    else if (b.length > a.length) j++;
    else { i++; j++; }
  }
  return edits + (a.length - i) + (b.length - j) <= 1;
}

// A query matches when every word matches some word of the product (prefix, or one typo
// for longer words), so "blu dream" and "GMO cookies" both find what you'd expect.
function matches(query, product) {
  const words = norm(query).split(" ").filter(Boolean);
  if (!words.length) return true;
  return words.every((q) => (q.length >= 4 && product._compact.includes(q)) || product._words.some((w) =>
    w.startsWith(q) || (q.length >= 5 && withinOneEdit(q, w))));
}

function effectiveDiscount(p) {
  const drop = p.price_drop_from ? Math.round(100 * (p.price_drop_from - p.price) / p.price_drop_from) : 0;
  return Math.max(p.discount_pct || 0, drop);
}

// ---------------------------------------------------------------- filtering

function inView(p) {
  switch (state.view) {
    case "deals": return effectiveDiscount(p) > 0 || !!p.deal;
    case "cheapest": return p.price_per_g != null;
    case "new": return p.is_new || p.back_in_stock;
    case "watch": return state.watch.some((term) => matches(term, p));
    default: return true;
  }
}

function passesFilters(p, { ignoreCategory = false } = {}) {
  const store = stores[p.store_id] || {};
  if (state.hiddenStores.has(p.store_id)) return false;
  if (!ignoreCategory && state.category !== "all" && p.category !== state.category) return false;
  if (state.distance && store.distance_mi != null && store.distance_mi > Number(state.distance)) return false;
  if (state.strainType && p.strain_type !== state.strainType) return false;
  if (state.saleOnly && effectiveDiscount(p) <= 0) return false;
  if (state.query && !matches(state.query, p)) return false;
  return true;
}

const nullsLast = (a, b) => (a == null) - (b == null) || (a ?? 0) - (b ?? 0);

function sorter() {
  const key = state.sort === "auto" ? VIEW_SORT[state.view] : state.sort;
  const dist = (p) => stores[p.store_id]?.distance_mi;
  return {
    ppg: (a, b) => nullsLast(a.price_per_g, b.price_per_g) || a.price - b.price,
    price: (a, b) => a.price - b.price,
    discount: (a, b) => effectiveDiscount(b) - effectiveDiscount(a) || nullsLast(a.price_per_g, b.price_per_g),
    thc: (a, b) => (b.thc ?? -1) - (a.thc ?? -1),
    newest: (a, b) => String(b.first_seen || "").localeCompare(String(a.first_seen || "")),
    distance: (a, b) => nullsLast(dist(a), dist(b)) || a.price - b.price,
  }[key];
}

// ---------------------------------------------------------------- rendering

function badge(text, cls) {
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

function card(p) {
  const store = stores[p.store_id] || {};
  const strainType = p.strain_type === "cbd" ? "CBD" : p.strain_type && p.strain_type[0].toUpperCase() + p.strain_type.slice(1);
  const meta = [p.brand, CATEGORY_LABELS[p.category], strainType,
    p.thc != null && `THC ${p.thc}%`].filter(Boolean).map(esc).join(" · ");
  const badges = [
    p.is_new && badge("NEW", "new"),
    p.back_in_stock && badge("BACK IN STOCK", "new"),
    p.discount_pct > 0 && badge(`SALE −${p.discount_pct}%`, "sale"),
    p.price_drop_from && badge(`↓ was ${money(p.price_drop_from)}`, "drop"),
    p.deal && badge(p.deal, "deal"),
  ].filter(Boolean).join("");
  const distance = store.distance_mi != null ? ` · ${store.distance_mi} mi` : "";
  return `<a class="item" href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener">
    <div class="info">
      <div class="name">${esc(p.name)}</div>
      <div class="meta">${meta}</div>
      <div class="where">${esc(store.name || p.store_id)}${distance}</div>
      ${badges ? `<div class="badges">${badges}</div>` : ""}
    </div>
    <div class="price">
      <div class="now">${money(p.price)}</div>
      ${p.original_price ? `<div class="was">${money(p.original_price)}</div>` : ""}
      <div class="size">${esc(p.size)}</div>
      ${p.price_per_g != null ? `<div class="ppg">${money(p.price_per_g)}/g</div>` : ""}
    </div>
  </a>`;
}

function renderCategories() {
  const counts = {};
  for (const p of menu.products) if (inView(p) && passesFilters(p, { ignoreCategory: true })) {
    counts[p.category] = (counts[p.category] || 0) + 1;
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const order = Object.keys(CATEGORY_LABELS).filter((c) => counts[c] || c === state.category);
  $("categories").innerHTML = [`<button data-cat="all" class="${state.category === "all" ? "on" : ""}">All <small>${total}</small></button>`]
    .concat(order.map((c) => `<button data-cat="${c}" class="${state.category === c ? "on" : ""}">${CATEGORY_LABELS[c]} <small>${counts[c] || 0}</small></button>`))
    .join("");
}

function renderStores() {
  const list = menu.stores.slice().sort((a, b) => nullsLast(a.distance_mi, b.distance_mi));
  const ok = list.filter((s) => s.status === "ok").length;
  $("stores-summary").textContent = `· ${ok} of ${list.length} up to date`;
  $("store-list").innerHTML = list.map((s) => `
    <li>
      <label>
        <input type="checkbox" data-store="${esc(s.id)}" ${state.hiddenStores.has(s.id) ? "" : "checked"}>
        <span class="dot ${esc(s.status || "error")}" title="${esc(s.status)}"></span>
        <span class="store-name">${esc(s.name)}</span>
      </label>
      <span class="store-meta">${s.distance_mi != null ? s.distance_mi + " mi · " : ""}${s.product_count} prices · ${s.scraped_at ? "updated " + ago(s.scraped_at) : "not scanned yet"}${
        s.menu_url ? ` · <a href="${esc(safeUrl(s.menu_url))}" target="_blank" rel="noopener">menu ↗</a>` : ""}${
        s.message ? `<em>${esc(s.message)}</em>` : ""}</span>
    </li>`).join("");
}

function renderWatchEditor() {
  $("watch-editor").hidden = state.view !== "watch";
  $("watch-chips").innerHTML = state.watch.map((term, i) =>
    `<button class="on" data-unwatch="${i}" title="Stop watching">${esc(term)} ✕</button>`).join("");
  const inStock = state.watch.filter((term) => menu.products.some((p) => !state.hiddenStores.has(p.store_id) && matches(term, p))).length;
  $("watch-count").hidden = !inStock;
  $("watch-count").textContent = inStock;
}

function renderWatchGroups(items) {
  if (!state.watch.length) {
    return `<p class="empty">Add strains you like above. They'll show here whenever a store near you has them.</p>`;
  }
  const sort = sorter();
  return state.watch.map((term) => {
    const hits = items.filter((p) => matches(term, p)).sort(sort);
    const storeCount = new Set(hits.map((p) => p.store_id)).size;
    const head = hits.length
      ? `${hits.length} in stock at ${storeCount} store${storeCount === 1 ? "" : "s"} · from ${money(Math.min(...hits.map((p) => p.price)))}`
      : "not on any menu right now";
    return `<section class="group"><h2>${esc(term)} <small>${head}</small></h2>${hits.slice(0, 40).map(card).join("")}</section>`;
  }).join("");
}

function render() {
  savePrefs();
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
  $("sort").value = state.sort;
  $("distance").value = state.distance;
  $("strain-type").value = state.strainType;
  $("sale-only").checked = state.saleOnly;
  renderCategories();
  renderStores();
  renderWatchEditor();

  const items = menu.products.filter((p) => inView(p) && passesFilters(p));
  if (state.view === "watch") {
    $("summary").textContent = "";
    $("results").innerHTML = renderWatchGroups(items);
    $("more").hidden = true;
    return;
  }
  items.sort(sorter());
  const storeCount = new Set(items.map((p) => p.store_id)).size;
  let summary = `${items.length} result${items.length === 1 ? "" : "s"} at ${storeCount} store${storeCount === 1 ? "" : "s"}`;
  if (state.query && items.length) {
    const cheapest = items.reduce((a, b) => (b.price < a.price ? b : a));
    summary += ` · cheapest ${money(cheapest.price)} (${cheapest.size}) at ${stores[cheapest.store_id]?.name || ""}`;
  }
  $("summary").textContent = summary;
  $("results").innerHTML = items.length
    ? items.slice(0, state.shown).map(card).join("")
    : `<p class="empty">Nothing matches. Try another category, a wider distance, or clearing the search.</p>`;
  $("more").hidden = items.length <= state.shown;
}

// ---------------------------------------------------------------- wiring

function bind() {
  $("tabs").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-view]");
    if (!button) return;
    state.view = button.dataset.view;
    state.shown = PAGE;
    if (state.view === "cheapest" && state.category === "all") state.category = "flower";
    render();
  });
  $("categories").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-cat]");
    if (!button) return;
    state.category = button.dataset.cat;
    state.shown = PAGE;
    render();
  });
  let timer;
  $("search").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.query = e.target.value; state.shown = PAGE; render(); }, 120);
  });
  $("sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
  $("distance").addEventListener("change", (e) => { state.distance = e.target.value; render(); });
  $("strain-type").addEventListener("change", (e) => { state.strainType = e.target.value; render(); });
  $("sale-only").addEventListener("change", (e) => { state.saleOnly = e.target.checked; render(); });
  $("store-list").addEventListener("change", (e) => {
    const id = e.target.dataset.store;
    if (!id) return;
    if (e.target.checked) state.hiddenStores.delete(id); else state.hiddenStores.add(id);
    render();
  });
  $("watch-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const term = $("watch-input").value.trim();
    if (term && !state.watch.some((t) => norm(t) === norm(term))) state.watch.push(term);
    $("watch-input").value = "";
    render();
  });
  $("watch-chips").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-unwatch]");
    if (!button) return;
    state.watch.splice(Number(button.dataset.unwatch), 1);
    render();
  });
  $("more").addEventListener("click", () => { state.shown += PAGE; render(); });
}

function showFreshness() {
  const hours = (Date.now() - new Date(menu.generated_at).getTime()) / 3600000;
  const el = $("freshness");
  el.hidden = false;
  el.textContent = `Updated ${ago(menu.generated_at)}`;
  el.classList.toggle("stale", hours > 24);
  if (hours > 24) el.title = "Run `python -m padeals scrape` to refresh";
  const origin = menu.origin?.label ? ` near ${menu.origin.label}` : "";
  $("subtitle").textContent = `${menu.products.length.toLocaleString()} prices from ${menu.stores.length} stores${origin}`;
}

async function start() {
  bind();
  try {
    const response = await fetch("data/menu.json", { cache: "no-store" });
    if (!response.ok) throw new Error(response.status);
    menu = await response.json();
  } catch (e) {
    $("subtitle").textContent = "No menu data yet";
    $("results").innerHTML = `<div class="empty"><p>No menu data yet. In a terminal, from the <code>pa-deals</code> folder, run:</p>
      <pre>python -m padeals setup\npython -m padeals scrape</pre>
      <p>then reload this page. (If you opened this file directly, use <code>python -m padeals serve</code> instead.)</p></div>`;
    return;
  }
  for (const s of menu.stores) stores[s.id] = s;
  for (const p of menu.products) {
    const text = norm(`${p.name} ${p.brand} ${p.strain}`);
    p._words = text.split(" ");
    p._compact = text.replace(/ /g, "");
  }
  showFreshness();
  render();
}

start();
