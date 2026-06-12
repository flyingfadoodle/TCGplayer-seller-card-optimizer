#!/usr/bin/env python3
"""
TCGPlayer Seller Scraper — MTG only
Cross-references the local catalog (from sync.py) to find exact product pages,
then scrapes seller listings and finds sellers who carry ALL requested cards.

Usage:
    # First sync catalog (once per day):
    python sync.py

    # Then search:
    python scraper.py --cards "Black Lotus" "Tropical Island"
    python scraper.py --cards "Black Lotus:Alpha" "Tropical Island:Unlimited"

    # Results saved as data/results.json — load in index.html
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("❌  pip install playwright && playwright install chromium")
    sys.exit(1)

CATALOG_DIR = Path("catalog")
DATA_DIR    = Path("data")

CONDITIONS = ["Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"]

PRINTING_TYPES = [
    "Extended Art", "Borderless", "Showcase", "Etched Foil", "Surge Foil",
    "Textured Foil", "Gilded Foil", "Galaxy Foil", "Serialized", "Retro Frame",
    "Step-and-Compleat Foil", "Phyrexian Language", "Halo Foil",
    "Oil Slick Raised Foil", "Double Rainbow Foil", "Confetti Foil", "Ripple Foil",
    "Foil", "Non-Foil",
]


# ── Catalog lookup ────────────────────────────────────────────────────────────

def load_index() -> list[dict]:
    path = CATALOG_DIR / "mtg" / "index.json"
    if not path.exists():
        print("❌  No catalog found. Run: python sync.py")
        return []
    data = json.loads(path.read_text())
    return data.get("index", [])


def find_products(index: list[dict], card_name: str, edition: str = None,
                  max_results: int = 8) -> list[dict]:
    q_name    = card_name.lower().strip()
    q_edition = edition.lower().strip() if edition else None

    scored = []
    for p in index:
        name  = p["name"].lower()
        set_  = p["set"].lower()
        clean = p["clean"].lower()

        if q_name not in name and q_name not in clean:
            continue
        if q_edition and q_edition not in name and q_edition not in set_:
            continue

        score = 0
        if name == q_name or clean == q_name:
            score = 100
        elif name.startswith(q_name) or clean.startswith(q_name):
            score = 80
        else:
            score = 60

        if q_edition:
            if q_edition in set_:
                score += 20
            elif q_edition in name:
                score += 10

        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:max_results]]


# ── Scraper ───────────────────────────────────────────────────────────────────

class Scraper:
    def __init__(self, headless=True):
        self.headless = headless
        self._pw = self._browser = self._page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        self._page = ctx.new_page()
        return self

    def __exit__(self, *_):
        if self._browser: self._browser.close()
        if self._pw:      self._pw.stop()

    def scrape_sellers(self, product: dict, max_sellers: int = 30) -> list[dict]:
        url = product.get("url")
        if not url:
            return []

        print(f"    🔗  {product['name']} ({product['set']})")
        print(f"        {url}")

        self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        self._dismiss_popups()
        self._page.wait_for_timeout(2_500)

        for label in ["All Sellers", "View All Listings", "All Listings"]:
            btn = self._page.query_selector(
                f"button:has-text('{label}'), a:has-text('{label}')"
            )
            if btn:
                btn.click()
                self._page.wait_for_timeout(1_500)
                break

        sellers = []
        try:
            self._page.wait_for_selector(
                ".seller-info__name, .listing-item__seller-name", timeout=12_000
            )
        except PWTimeout:
            print("        ⚠️   Could not load seller listings.")
            return sellers

        rows = self._page.query_selector_all(
            ".listing-item, .product-listing, [class*='listing-item']"
        )

        for row in rows[:max_sellers]:
            try:
                def t(sel):
                    el = row.query_selector(sel)
                    return el.inner_text().strip() if el else "N/A"

                seller    = t(".seller-info__name, .listing-item__seller-name, [class*='seller-name']")
                price     = t(".listing-item__listing-data--price, [class*='listing-price'], .price")
                condition = t(".condition-label, [class*='condition']")
                shipping  = t("[class*='shipping']")
                qty       = t("[class*='quantity'], [class*='qty']")

                if seller == "N/A" and price == "N/A":
                    continue

                price_f  = _parse_price(price)
                ship     = _parse_shipping(shipping, price_f)
                landed   = price_f + max(ship["shipping_cost"], 0)
                printing = _detect_printing(product["name"], product["set"])

                sellers.append({
                    "product_id":              product["id"],
                    "card_name":               product["name"],
                    "set":                     product["set"],
                    "game":                    "mtg",
                    "image":                   product.get("image", ""),
                    "rarity":                  product.get("rarity", ""),
                    "printing":                printing,
                    "card_url":                url,
                    "search_key":              product.get("search_key", ""),
                    "seller":                  seller,
                    "price":                   price,
                    "price_float":             price_f,
                    "condition":               condition,
                    "shipping_raw":            shipping,
                    "shipping_display":        ship["display"],
                    "shipping_cost":           ship["shipping_cost"],
                    "shipping_free":           ship["free"],
                    "shipping_free_threshold": ship["free_threshold"],
                    "shipping_qualifies":      ship["qualifies"],
                    "landed_cost":             landed,
                    "landed_display":          f"${landed:.2f}" if landed > 0 else "N/A",
                    "quantity":                qty,
                })
            except Exception as e:
                print(f"        ⚠️  Row error: {e}")

        print(f"        → {len(sellers)} listings scraped")
        return sellers

    def _dismiss_popups(self):
        for sel in [
            "button[aria-label='Close']", ".modal-close", "[class*='close-button']",
            "button:has-text('Accept')", "button:has-text('OK')",
        ]:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self._page.wait_for_timeout(400)
            except Exception:
                pass


# ── Combo matching ────────────────────────────────────────────────────────────

def find_combos(sellers: list[dict], search_keys: list[str]) -> list[dict]:
    by_seller: dict[str, dict] = {}
    for s in sellers:
        name = s["seller"]
        key  = s["search_key"]
        if name not in by_seller:
            by_seller[name] = {}
        if key not in by_seller[name] or s["landed_cost"] < by_seller[name][key]["landed_cost"]:
            by_seller[name][key] = s

    combos = []
    for seller, by_key in by_seller.items():
        if not all(k in by_key for k in search_keys):
            continue
        listings        = [by_key[k] for k in search_keys]
        total_price     = sum(l["price_float"]  for l in listings)
        total_shipping  = sum(max(l["shipping_cost"], 0) for l in listings)
        total_landed    = sum(l["landed_cost"]   for l in listings)
        combos.append({
            "seller":                  seller,
            "listings":                listings,
            "total_price":             total_price,
            "total_shipping":          total_shipping,
            "total_landed":            total_landed,
            "total_price_display":     f"${total_price:.2f}",
            "total_shipping_display":  f"${total_shipping:.2f}",
            "total_landed_display":    f"${total_landed:.2f}",
            "all_shipping_covered":    all(l["shipping_qualifies"] for l in listings),
            "any_shipping_covered":    any(l["shipping_qualifies"] for l in listings),
            "cards_count":             len(listings),
        })

    combos.sort(key=lambda c: (c["total_landed"] == 0, c["total_landed"]))
    return combos


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(s: str) -> float:
    try:
        return float(s.replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


def _parse_shipping(raw: str, item_price: float) -> dict:
    s   = raw.strip() if raw else ""
    low = s.lower()
    out = {"free": False, "free_threshold": None, "qualifies": False,
           "shipping_cost": -1.0, "display": s or "N/A"}
    if not s or s == "N/A":
        return out
    m = re.search(r'\$\s*([\d,]+\.?\d*)', low)
    if m and re.search(r'free|ship', low):
        t = float(m.group(1).replace(",", ""))
        q = item_price >= t
        out.update(free=False, free_threshold=t, qualifies=q,
                   shipping_cost=0.0 if q else -1.0,
                   display=f"Free over ${t:.2f}" + (" ✓" if q else ""))
        return out
    if re.search(r'\$\s*0\.00', s):
        out.update(free=False, free_threshold=0.0, qualifies=True,
                   shipping_cost=0.0, display="Covered ($0.00)")
        return out
    cost_m = re.search(r'\$\s*([\d,]+\.?\d*)', s)
    if cost_m:
        c = float(cost_m.group(1).replace(",", ""))
        out.update(shipping_cost=c, display=f"+${c:.2f}")
        return out
    return out


def _detect_printing(name: str, set_str: str) -> str:
    combined = f"{name} {set_str}".lower()
    CHECKS = [
        ("Extended Art",   ["extended art"]),
        ("Borderless",     ["borderless"]),
        ("Showcase",       ["showcase"]),
        ("Etched Foil",    ["etched foil"]),
        ("Surge Foil",     ["surge foil"]),
        ("Textured Foil",  ["textured foil"]),
        ("Gilded Foil",    ["gilded foil"]),
        ("Galaxy Foil",    ["galaxy foil"]),
        ("Serialized",     ["serialized"]),
        ("Retro Frame",    ["retro frame"]),
        ("Foil",           ["foil"]),
    ]
    for label, kws in CHECKS:
        if any(kw in combined for kw in kws):
            return label
    return ""


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_card_arg(s: str):
    if ":" in s:
        p = s.split(":", 1)
        return p[0].strip(), p[1].strip()
    return s.strip(), None


def main():
    ap = argparse.ArgumentParser(
        description="Scrape TCGPlayer sellers for MTG cards."
    )
    ap.add_argument("--cards",       nargs="+", required=True,
                    help="Cards: 'Name' or 'Name:Edition'")
    ap.add_argument("--max-sellers", type=int, default=30)
    ap.add_argument("--max-results", type=int, default=5)
    ap.add_argument("--output",      type=str, default="data/results.json")
    ap.add_argument("--visible",     action="store_true")
    ap.add_argument("--no-sellers",  action="store_true")
    args = ap.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    print(f"\nLoading MTG catalog…")
    index = load_index()
    if not index:
        return
    print(f"  {len(index):,} products loaded")

    card_requests     = [parse_card_arg(c) for c in args.cards]
    selected_products = []
    search_keys       = []

    for card_name, edition in card_requests:
        print(f"\n🔍  '{card_name}'" + (f" [{edition}]" if edition else ""))
        matches = find_products(index, card_name, edition, args.max_results)

        if not matches:
            print("    ⚠️   No matches in catalog. Run sync.py first.")
            continue

        chosen = matches[0]
        sk = f"{card_name}|{edition or ''}"
        chosen["search_key"] = sk
        selected_products.append(chosen)
        search_keys.append(sk)

        print(f"    ✓  Matched: {chosen['name']} ({chosen['set']})")
        if len(matches) > 1:
            print(f"       Other matches:")
            for m in matches[1:]:
                print(f"         • {m['name']} ({m['set']})")

    all_sellers = []
    if not args.no_sellers and selected_products:
        print(f"\n{'═'*56}")
        print(f"  Scraping seller listings…")
        print(f"{'═'*56}")
        with Scraper(headless=not args.visible) as s:
            for product in selected_products:
                sellers = s.scrape_sellers(product, args.max_sellers)
                all_sellers.extend(sellers)
                time.sleep(0.5)

    combos = find_combos(all_sellers, search_keys) if all_sellers else []

    print(f"\n{'═'*56}")
    print(f"  Cards matched:   {len(selected_products)}")
    print(f"  Seller listings: {len(all_sellers)}")
    print(f"  Combo sellers:   {len(combos)}")
    if combos:
        print(f"\n  Top bundle deals:")
        for i, c in enumerate(combos[:5], 1):
            print(f"    {i}. {c['seller']:<30} {c['total_landed_display']}")
    print(f"{'═'*56}\n")

    out = Path(args.output)
    out.parent.mkdir(exist_ok=True)
    payload = {
        "game":        "mtg",
        "search_keys": search_keys,
        "products":    selected_products,
        "sellers":     all_sellers,
        "combos":      combos,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"💾  {out}  →  load in index.html\n")


if __name__ == "__main__":
    main()
