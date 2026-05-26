#!/usr/bin/env python3
"""
TCGPlayer Card & Seller Scraper — v2
Supports specific card versions/editions and multi-card combination searches.

Usage:
    # Single card
    python scraper.py --cards "Black Lotus:Alpha" --game mtg --output lotus.json

    # Combination search (finds sellers who carry ALL listed cards)
    python scraper.py --cards "Tropical Island:Unlimited" "Black Lotus:Alpha" --game mtg --output combo.json

    # Pokémon
    python scraper.py --cards "Charizard:Base Set" "Blastoise:Base Set Shadowless" --game pokemon --output starters.json

    # Free-text version override
    python scraper.py --cards "Lightning Bolt" --game mtg --version "4th Edition" --output bolt.json
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


# ── Edition / version data ────────────────────────────────────────────────────

MTG_SETS = [
    "Alpha", "Beta", "Unlimited", "Revised", "4th Edition", "5th Edition",
    "6th Edition", "7th Edition", "8th Edition", "9th Edition", "10th Edition",
    "Arabian Nights", "Antiquities", "Legends", "The Dark", "Fallen Empires",
    "Ice Age", "Homelands", "Alliances", "Mirage", "Visions", "Weatherlight",
    "Tempest", "Stronghold", "Exodus", "Urza's Saga", "Urza's Legacy",
    "Urza's Destiny", "Mercadian Masques", "Nemesis", "Prophecy",
    "Invasion", "Planeshift", "Apocalypse", "Odyssey", "Torment", "Judgment",
    "Onslaught", "Legions", "Scourge", "Mirrodin", "Darksteel", "Fifth Dawn",
    "Champions of Kamigawa", "Ravnica", "Innistrad", "Return to Ravnica",
    "Theros", "Khans of Tarkir", "Battle for Zendikar", "Shadows over Innistrad",
    "Kaladesh", "Amonkhet", "Ixalan", "Guilds of Ravnica", "War of the Spark",
    "Throne of Eldraine", "Ikoria", "Kaldheim", "Strixhaven", "Innistrad: Midnight Hunt",
    "Kamigawa: Neon Dynasty", "Streets of New Capenna", "The Brothers' War",
    "March of the Machine", "Wilds of Eldraine", "The Lost Caverns of Ixalan",
    "Murders at Karlov Manor", "Outlaws of Thunder Junction", "Bloomburrow",
    "Duskmourn", "Modern Horizons", "Modern Horizons 2", "Modern Horizons 3",
    "Commander", "Double Masters", "Jumpstart",
]

POKEMON_SETS = [
    "Base Set", "Base Set Shadowless", "Base Set 1st Edition",
    "Jungle", "Fossil", "Team Rocket", "Gym Heroes", "Gym Challenge",
    "Neo Genesis", "Neo Discovery", "Neo Revelation", "Neo Destiny",
    "Legendary Collection", "Expedition", "Aquapolis", "Skyridge",
    "Ruby & Sapphire", "Sandstorm", "Dragon", "Team Magma vs Team Aqua",
    "Hidden Legends", "FireRed & LeafGreen", "Team Rocket Returns",
    "Deoxys", "Emerald", "Unseen Forces", "Delta Species",
    "Legend Maker", "Holon Phantoms", "Crystal Guardians",
    "Dragon Frontiers", "Power Keepers",
    "Diamond & Pearl", "Mysterious Treasures", "Secret Wonders",
    "Great Encounters", "Majestic Dawn", "Legends Awakened",
    "Stormfront", "Platinum", "Rising Rivals", "Supreme Victors", "Arceus",
    "HeartGold SoulSilver", "Unleashed", "Undaunted", "Triumphant",
    "Call of Legends", "Black & White", "Emerging Powers", "Noble Victories",
    "Next Destinies", "Dark Explorers", "Dragons Exalted",
    "Boundaries Crossed", "Plasma Storm", "Plasma Freeze", "Plasma Blast",
    "Legendary Treasures", "XY", "Flashfire", "Furious Fists",
    "Phantom Forces", "Primal Clash", "Roaring Skies", "Ancient Origins",
    "BREAKthrough", "BREAKpoint", "Fates Collide", "Steam Siege",
    "Evolutions", "Sun & Moon", "Guardians Rising", "Burning Shadows",
    "Crimson Invasion", "Ultra Prism", "Forbidden Light", "Celestial Storm",
    "Lost Thunder", "Team Up", "Unbroken Bonds", "Unified Minds",
    "Cosmic Eclipse", "Sword & Shield", "Rebel Clash", "Darkness Ablaze",
    "Champion's Path", "Vivid Voltage", "Battle Styles", "Chilling Reign",
    "Evolving Skies", "Fusion Strike", "Brilliant Stars", "Astral Radiance",
    "Lost Origin", "Silver Tempest", "Crown Zenith",
    "Scarlet & Violet", "Paldea Evolved", "Obsidian Flames",
    "Paradox Rift", "Paldean Fates", "Temporal Forces", "Twilight Masquerade",
    "Shrouded Fable", "Stellar Crown", "Surging Sparks", "Prismatic Evolutions",
    "Destined Rivals",
]

GAMES = {
    "pokemon": {
        "label": "Pokémon",
        "sets": POKEMON_SETS,
        "search_url": "https://www.tcgplayer.com/search/pokemon/product?q={query}&view=grid",
    },
    "mtg": {
        "label": "Magic: The Gathering",
        "sets": MTG_SETS,
        "search_url": "https://www.tcgplayer.com/search/magic/product?q={query}&view=grid",
    },
}

CONDITIONS = ["Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"]


# ── Scraper ───────────────────────────────────────────────────────────────────

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

    # ── Search with optional set filter ──────────────────────────────────

    def search_cards(self, card_name: str, game: str, edition: str = None,
                     max_cards: int = 8) -> list[dict]:
        """Search for a card, optionally filtered to a specific set/edition."""
        cfg = GAMES[game]
        query = card_name
        if edition:
            query = f"{card_name} {edition}"

        url = cfg["search_url"].format(query=quote_plus(query))
        print(f"\n  🔍  '{card_name}'" + (f" [{edition}]" if edition else "") + f"  →  {url}")

        self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        self._dismiss_popups()
        self._page.wait_for_timeout(2_500)

        cards = []
        try:
            self._page.wait_for_selector(".search-result", timeout=15_000)
        except PlaywrightTimeout:
            print(f"    ⚠️   No results found.")
            return cards

        items = self._page.query_selector_all(".search-result")

        for item in items[:max_cards]:
            try:
                def gtxt(sel):
                    el = item.query_selector(sel)
                    return el.inner_text().strip() if el else "N/A"

                name  = gtxt(".search-result__title")
                price = gtxt(".search-result__market-price--value")
                set_  = gtxt(".search-result__subtitle")
                link_el = item.query_selector("a.search-result__image, a[href*='/product/']")
                href  = link_el.get_attribute("href") if link_el else None
                link  = ("https://www.tcgplayer.com" + href if href and href.startswith("/") else href or "N/A")

                # Filter to requested edition if provided
                if edition and edition.lower() not in set_.lower() and edition.lower() not in name.lower():
                    continue

                cards.append({
                    "game": cfg["label"], "name": name, "set": set_,
                    "edition": edition or "", "market_price": price, "url": link,
                    "search_key": f"{card_name}|{edition or ''}",
                })
            except Exception as e:
                print(f"    ⚠️   Row error: {e}")

        print(f"    → {len(cards)} card(s) found")
        return cards

    # ── Sellers ───────────────────────────────────────────────────────────

    def get_sellers(self, card: dict, max_sellers: int = 25) -> list[dict]:
        if card["url"] == "N/A":
            return []

        print(f"    📦  Sellers for: {card['name']} ({card['set']})")
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
            print("        ⚠️   Could not load listings.")
            return sellers

        rows = self._page.query_selector_all(
            ".listing-item, .product-listing, [class*='listing-item']"
        )

        for row in rows[:max_sellers]:
            try:
                def rtxt(sel):
                    el = row.query_selector(sel)
                    return el.inner_text().strip() if el else "N/A"

                seller    = rtxt(".seller-info__name, .listing-item__seller-name, [class*='seller-name']")
                price     = rtxt(".listing-item__listing-data--price, [class*='listing-price'], .price")
                condition = rtxt(".condition-label, [class*='condition']")
                shipping  = rtxt("[class*='shipping']")
                qty       = rtxt("[class*='quantity'], [class*='qty']")

                if seller == "N/A" and price == "N/A":
                    continue

                # Parse price to float for sorting
                price_float = _parse_price(price)

                sellers.append({
                    "card_name":    card["name"],
                    "set":          card["set"],
                    "edition":      card["edition"],
                    "game":         card["game"],
                    "search_key":   card["search_key"],
                    "seller":       seller,
                    "price":        price,
                    "price_float":  price_float,
                    "condition":    condition,
                    "shipping":     shipping,
                    "quantity":     qty,
                    "card_url":     card["url"],
                })
            except Exception as e:
                print(f"        ⚠️   Row error: {e}")

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


# ── Combination matching ──────────────────────────────────────────────────────

def find_seller_combos(sellers: list[dict], search_keys: list[str]) -> list[dict]:
    """
    Find sellers who appear in listings for ALL requested search_keys.
    Returns ranked list of (seller, cards, total_price).
    """
    if not sellers or not search_keys:
        return []

    # Group by seller
    by_seller: dict[str, dict] = {}
    for s in sellers:
        name = s["seller"]
        if name not in by_seller:
            by_seller[name] = {}
        key = s["search_key"]
        # Keep cheapest listing per card per seller
        if key not in by_seller[name] or s["price_float"] < by_seller[name][key]["price_float"]:
            by_seller[name][key] = s

    combos = []
    for seller, cards_by_key in by_seller.items():
        # Only include sellers who have ALL requested cards
        if all(k in cards_by_key for k in search_keys):
            listings = [cards_by_key[k] for k in search_keys]
            total = sum(c["price_float"] for c in listings if c["price_float"] > 0)
            combos.append({
                "seller":       seller,
                "listings":     listings,
                "total_price":  total,
                "total_display": f"${total:.2f}" if total > 0 else "N/A",
                "cards_count":  len(listings),
            })

    # Sort cheapest bundle first
    combos.sort(key=lambda c: (c["total_price"] == 0, c["total_price"]))
    return combos


def _parse_price(price_str: str) -> float:
    try:
        return float(price_str.replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_card_arg(s: str):
    """Parse 'Card Name:Edition' → (card_name, edition)"""
    if ":" in s:
        parts = s.split(":", 1)
        return parts[0].strip(), parts[1].strip()
    return s.strip(), None


def main():
    ap = argparse.ArgumentParser(
        description="Scrape TCGPlayer — find sellers with specific card versions and combinations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py --cards "Black Lotus:Alpha" --game mtg --output lotus.json
  python scraper.py --cards "Tropical Island:Unlimited" "Black Lotus:Alpha" --game mtg --output combo.json
  python scraper.py --cards "Charizard:Base Set" "Blastoise:Base Set Shadowless" --game pokemon --output bundle.json
        """
    )
    ap.add_argument("--cards",       nargs="+", required=True,
                    help="Cards to search. Format: 'Name:Edition' or just 'Name'")
    ap.add_argument("--game",        choices=["pokemon", "mtg"], required=True)
    ap.add_argument("--max-cards",   type=int, default=5,
                    help="Max search results per card (default 5)")
    ap.add_argument("--max-sellers", type=int, default=30,
                    help="Max seller listings per card (default 30)")
    ap.add_argument("--output",      type=str, default="data.json",
                    help="Output JSON file (default: data.json)")
    ap.add_argument("--no-sellers",  action="store_true")
    ap.add_argument("--visible",     action="store_true")
    args = ap.parse_args()

    card_requests = [parse_card_arg(c) for c in args.cards]
    search_keys   = [f"{name}|{edition or ''}" for name, edition in card_requests]

    print(f"\n{'═'*60}")
    print(f"  TCGPlayer Combo Scraper")
    print(f"  Game: {GAMES[args.game]['label']}")
    print(f"  Cards requested:")
    for name, edition in card_requests:
        print(f"    • {name}" + (f"  [{edition}]" if edition else ""))
    print(f"{'═'*60}")

    all_cards   = []
    all_sellers = []

    with TCGPlayerScraper(headless=not args.visible) as scraper:
        for name, edition in card_requests:
            print(f"\n── Searching: {name}" + (f" [{edition}]" if edition else ""))
            cards = scraper.search_cards(name, args.game, edition, args.max_cards)
            all_cards.extend(cards)

            if not args.no_sellers:
                for card in cards:
                    s = scraper.get_sellers(card, args.max_sellers)
                    all_sellers.extend(s)
                    time.sleep(0.5)

    # Combo matching
    combos = find_seller_combos(all_sellers, search_keys) if not args.no_sellers else []

    # Summary
    print(f"\n{'═'*60}")
    print(f"  Cards found: {len(all_cards)}")
    print(f"  Seller listings: {len(all_sellers)}")
    print(f"  Sellers with ALL cards: {len(combos)}")
    if combos:
        print(f"\n  Top bundle deals:")
        for i, c in enumerate(combos[:5], 1):
            print(f"    {i}. {c['seller']:30s}  →  {c['total_display']}")
    print(f"{'═'*60}\n")

    # Save
    out = Path(args.output).with_suffix(".json")
    payload = {
        "game":        GAMES[args.game]["label"],
        "search_keys": search_keys,
        "cards":       all_cards,
        "sellers":     all_sellers,
        "combos":      combos,
        "sets": {
            "mtg":     MTG_SETS,
            "pokemon": POKEMON_SETS,
        },
        "conditions":  CONDITIONS,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"💾  Saved → {out}")
    print(f"    Open index.html in your browser and load this file.\n")


if __name__ == "__main__":
    main()
