#!/usr/bin/env python3
"""
TCGPlayer Catalog Sync — powered by TCGCSV
Pulls the full MTG card catalog from TCGCSV (mirrors TCGPlayer's API).
Run this once per day. Creates catalog/mtg/index.json.

Usage:
    python sync.py
    python sync.py --sets-only      # only pull set list, skip products (fast)
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests

CATALOG_DIR = Path("catalog")
TCGCSV      = "https://tcgcsv.com/tcgplayer"
UA          = "TCGOptimizerSync/1.0"
HEADERS     = {"User-Agent": UA, "Accept": "application/json"}

MTG_CATEGORY_ID = 1


def get(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(0.12)
    return r.json()


def sync_mtg(sets_only: bool = False):
    cat     = MTG_CATEGORY_ID
    out_dir = CATALOG_DIR / "mtg"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*56}")
    print(f"  Syncing Magic: The Gathering (categoryId={cat})")
    print(f"{'═'*56}")

    print("  Fetching sets…")
    groups_data = get(f"{TCGCSV}/{cat}/groups")
    groups = groups_data.get("results", [])
    print(f"  → {len(groups)} sets found")

    (out_dir / "groups.json").write_text(
        json.dumps({"groups": groups, "game": "mtg", "categoryId": cat}, indent=2)
    )

    if sets_only:
        print("  Sets-only mode — skipping products.")
        return

    all_products = []
    all_prices   = []

    for i, group in enumerate(groups, 1):
        gid  = group["groupId"]
        name = group["name"]
        print(f"  [{i:3}/{len(groups)}] {name[:50]:<50}", end="", flush=True)

        try:
            prod_data  = get(f"{TCGCSV}/{cat}/{gid}/products")
            products   = prod_data.get("results", [])
            price_data = get(f"{TCGCSV}/{cat}/{gid}/prices")
            prices     = price_data.get("results", [])

            for p in products:
                p["groupName"]  = name
                p["game"]       = "mtg"
                p["categoryId"] = cat

            all_products.extend(products)
            all_prices.extend(prices)
            print(f"  {len(products):4} cards, {len(prices):4} prices")

        except Exception as e:
            print(f"  ⚠️  Error: {e}")

    print(f"\n  Saving {len(all_products):,} products…")
    (out_dir / "products.json").write_text(
        json.dumps({"products": all_products, "game": "mtg"}, indent=2, ensure_ascii=False)
    )

    print(f"  Saving {len(all_prices):,} prices…")
    (out_dir / "prices.json").write_text(
        json.dumps({"prices": all_prices, "game": "mtg"}, indent=2, ensure_ascii=False)
    )

    print("  Building search index…")
    price_map = {}
    for p in all_prices:
        pid  = p.get("productId")
        sub  = p.get("subTypeName", "Normal")
        cond = p.get("condition", {})
        if pid not in price_map:
            price_map[pid] = {}
        key = f"{sub}"
        if key not in price_map[pid]:
            price_map[pid][key] = {}
        price_map[pid][key][cond.get("name", "?")] = {
            "market":    p.get("marketPrice"),
            "low":       p.get("lowPrice"),
            "mid":       p.get("midPrice"),
            "high":      p.get("highPrice"),
            "directLow": p.get("directLowPrice"),
        }

    index = []
    for p in all_products:
        pid    = p["productId"]
        prices = price_map.get(pid, {})
        ext    = {e["name"]: e["value"] for e in p.get("extendedData", [])}
        index.append({
            "id":      pid,
            "name":    p["name"],
            "clean":   p.get("cleanName", p["name"]),
            "set":     p.get("groupName", ""),
            "groupId": p.get("groupId"),
            "image":   p.get("imageUrl", ""),
            "url":     p.get("url", ""),
            "game":    "mtg",
            "rarity":  ext.get("Rarity", ""),
            "number":  ext.get("Number", ""),
            "type":    ext.get("Card Type", ext.get("Type", "")),
            "prices":  prices,
        })

    (out_dir / "index.json").write_text(
        json.dumps({"index": index, "game": "mtg", "count": len(index)}, indent=2, ensure_ascii=False)
    )
    print(f"  ✅ MTG index: {len(index):,} cards")


def main():
    ap = argparse.ArgumentParser(description="Sync MTG catalog via TCGCSV")
    ap.add_argument("--sets-only", action="store_true", help="Only pull set list (fast)")
    args = ap.parse_args()

    CATALOG_DIR.mkdir(exist_ok=True)
    sync_mtg(sets_only=args.sets_only)
    print(f"\n✅  Sync complete.\n")


if __name__ == "__main__":
    main()
