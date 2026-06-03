# TCG Optimizer

A TCGPlayer-style card search and seller optimizer for Magic: The Gathering and Pokémon. Find sellers who carry **all** cards on your list, ranked by total landed cost.

---

## Quick Start

### Step 1 — Install dependencies
```bash
pip install playwright requests
playwright install chromium
```

### Step 2 — Sync the card catalog (once per day)
```bash
python sync.py --game pokemon    # ~5 min, pulls all Pokémon cards
python sync.py --game mtg        # ~15 min, pulls all MTG cards
python sync.py                   # both games
```

This creates `catalog/pokemon/index.json` and `catalog/mtg/index.json`.

### Step 3 — Scrape sellers for your cards
```bash
# Single card
python scraper.py --cards "Charizard:Base Set" --game pokemon

# Multiple cards — finds sellers with ALL of them
python scraper.py \
  --cards "Black Lotus:Alpha" "Tropical Island:Unlimited" \
  --game mtg --output data/results.json

# Pokémon combo
python scraper.py \
  --cards "Charizard:Base Set 1st Edition" "Blastoise:Base Set Shadowless" \
  --game pokemon
```

### Step 4 — Open the UI
Open `index.html` in your browser, then:
- Load `catalog/pokemon/index.json` for fast card autocomplete with images + market prices
- Load `data/results.json` to see seller listings and bundle finder

---

## Features

| Feature | Details |
|---|---|
| **Catalog-powered autocomplete** | Searches your local TCGCSV catalog with card images, set names, printing variants, and market prices |
| **Exact URL matching** | Uses `productId` from the catalog to go directly to the right TCGPlayer listing page |
| **Bundle Finder** | Finds sellers who carry ALL your cards, ranked by total landed cost (price + shipping) |
| **Card images** | Shows TCGPlayer card images throughout |
| **Market prices** | Low / Mid / Market / High from the catalog |
| **Rarity badges** | Common, Uncommon, Rare, Mythic, Ultra Rare, Secret Rare |
| **Printing detection** | Extended Art, Borderless, Showcase, Foil, 1st Edition, etc. |
| **Condition filter** | NM / LP+ / MP+ / HP+ / Any |
| **Shipping detection** | Detects $5+ free shipping threshold, shows landed cost |
| **Export** | CSV and JSON from the browser |

---

## Scraper Options

| Flag | Default | Description |
|---|---|---|
| `--cards` | required | `"Name"` or `"Name:Edition"` |
| `--game` | required | `pokemon` or `mtg` |
| `--max-sellers` | `30` | Seller listings per card |
| `--max-results` | `5` | Catalog matches to show per card |
| `--output` | `data/results.json` | Output file |
| `--visible` | off | Show browser window |
| `--no-sellers` | off | Skip scraping (catalog lookup only) |

---

## Notes
- TCGCSV updates daily. Run `sync.py` once per day for fresh prices.
- Seller listings are live-scraped from TCGPlayer via Playwright.
- For personal/research use. See [TCGPlayer's ToS](https://help.tcgplayer.com/hc/en-us/articles/221672947).
