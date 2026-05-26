#!/usr/bin/env python3
"""
TCGPlayer Card & Seller Scraper
Scrapes tcgplayer.com for MTG and Pokémon cards and their seller listings.

Usage:
    python scraper.py "Charizard" --game pokemon
    python scraper.py "Black Lotus" --game mtg --output data.json
    python scraper.py "Pikachu" --game pokemon --max-sellers 20 --output pikachu.json

Then open index.html in your browser and load the .json file.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("❌  Playwright not installed.\n    Run: pip install playwright && playwright install chromium")
    sys.exit(1)


GAMES = {
    "pokemon": {
        "label": "Pokémon",
        "search_url": "https://www.tcgplayer.com/search/pokemon/product?q={query}&view=grid",
    },
    "mtg": {
        "label": "Magic: The Gathering",
        "search_url": "https://www.tcgplayer.com/search/magic/product?q={query}&view=grid",
    },
}


class TCGPlayerScraper:
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

    # ── Search ────────────────────────────────────────────────────────────

    def search_cards(self, query: str, game: str, max_cards: int = 10) -> list[dict]:
        cfg = GAMES[game]
        url = cfg["search_url"].format(query=quote_plus(query))
        print(f"\n🔍  Searching {cfg['label']} for: '{query}'")
        print(f"    {url}")

        self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        self._dismiss_popups()
        self._page.wait_for_timeout(2_500)

        cards = []
        try:
            self._page.wait_for_selector(".search-result", timeout=15_000)
        except PlaywrightTimeout:
            print("    ⚠️  No results found (or TCGPlayer changed their layout).")
            return cards

        items = self._page.query_selector_all(".search-result")
        print(f"    Found {len(items)} result(s). Collecting up to {max_cards}…")

        for item in items[:max_cards]:
            try:
                name_el  = item.query_selector(".search-result__title")
                price_el = item.query_selector(".search-result__market-price--value")
                set_el   = item.query_selector(".search-result__subtitle")
                link_el  = item.query_selector("a.search-result__image, a[href*='/product/']")

                name  = (name_el.inner_text().strip()  if name_el  else "N/A")
                price = (price_el.inner_text().strip() if price_el else "N/A")
                set_  = (set_el.inner_text().strip()   if set_el   else "N/A")
                href  = (link_el.get_attribute("href") if link_el  else None)
                link  = ("https://www.tcgplayer.com" + href if href and href.startswith("/") else href or "N/A")

                cards.append({"game": cfg["label"], "name": name, "set": set_,
                               "market_price": price, "url": link})
            except Exception as e:
                print(f"    ⚠️  Error parsing a result: {e}")

        return cards

    # ── Sellers ───────────────────────────────────────────────────────────

    def get_sellers(self, card: dict, max_sellers: int = 10) -> list[dict]:
        if card["url"] == "N/A":
            return []
        print(f"    📦  Sellers for: {card['name']}")
        self._page.goto(card["url"], wait_until="domcontentloaded", timeout=30_000)
        self._dismiss_popups()
        self._page.wait_for_timeout(2_000)

        for label in ["All Sellers", "View All Listings", "All Listings"]:
            btn = self._page.query_selector(f"button:has-text('{label}'), a:has-text('{label}')")
            if btn:
                btn.click()
                self._page.wait_for_timeout(1_500)
                break

        sellers = []
        try:
            self._page.wait_for_selector(
                ".seller-info__name, .listing-item__seller-name", timeout=12_000
            )
        except PlaywrightTimeout:
            print("        ⚠️  Could not load seller listings.")
            return sellers

        rows = self._page.query_selector_all(
            ".listing-item, .product-listing, [class*='listing-item']"
        )
        for row in rows[:max_sellers]:
            try:
                def txt(sel):
                    el = row.query_selector(sel)
                    return el.inner_text().strip() if el else "N/A"

                seller    = txt(".seller-info__name, .listing-item__seller-name, [class*='seller-name']")
                price     = txt(".listing-item__listing-data--price, [class*='listing-price'], .price")
                condition = txt(".condition-label, [class*='condition']")
                shipping  = txt("[class*='shipping']")
                qty       = txt("[class*='quantity'], [class*='qty']")

                if seller == "N/A" and price == "N/A":
                    continue

                sellers.append({
                    "card_name": card["name"], "set": card["set"], "game": card["game"],
                    "seller": seller, "price": price, "condition": condition,
                    "shipping": shipping, "quantity": qty, "card_url": card["url"],
                })
            except Exception as e:
                print(f"        ⚠️  Row error: {e}")

        print(f"        → {len(sellers)} listing(s)")
        return sellers

    def _dismiss_popups(self):
        for sel in [
            "#onetrust-accept-btn-handler",
            "button[class*='accept']",
            "button:has-text('Accept')",
            "button:has-text('Close')",
        ]:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self._page.wait_for_timeout(400)
            except Exception:
                pass


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Scrape TCGPlayer cards and sellers.")
    ap.add_argument("query",           help="Card name, e.g. 'Charizard'")
    ap.add_argument("--game",          choices=["pokemon","mtg"], required=True)
    ap.add_argument("--max-cards",     type=int, default=10)
    ap.add_argument("--max-sellers",   type=int, default=10)
    ap.add_argument("--output",        type=str, default=None,
                    help="Save results as JSON (e.g. data.json). Load in index.html.")
    ap.add_argument("--no-sellers",    action="store_true", help="Skip seller listings")
    ap.add_argument("--visible",       action="store_true", help="Show browser window")
    args = ap.parse_args()

    with TCGPlayerScraper(headless=not args.visible) as scraper:
        cards = scraper.search_cards(args.query, args.game, args.max_cards)

        sellers = []
        if not args.no_sellers and cards:
            print(f"\n🏪  Fetching sellers for {len(cards)} card(s)…")
            for card in cards:
                sellers.extend(scraper.get_sellers(card, args.max_sellers))
                time.sleep(0.5)

    # Print summary
    print(f"\n{'═'*55}")
    print(f"  Cards: {len(cards)}   |   Seller listings: {len(sellers)}")
    print(f"{'═'*55}")
    for c in cards:
        print(f"  🃏  {c['name']}  —  {c['set']}  —  {c['market_price']}")

    # Save
    if args.output:
        out = Path(args.output).with_suffix(".json")
        out.write_text(json.dumps({"cards": cards, "sellers": sellers}, indent=2, ensure_ascii=False))
        print(f"\n💾  Saved → {out}")
        print(f"    Open index.html in your browser and load this file.\n")
    else:
        print("\n💡  Tip: add --output data.json to save results for the web UI.\n")


if __name__ == "__main__":
    main()
