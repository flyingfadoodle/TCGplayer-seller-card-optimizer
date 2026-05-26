# TCGPlayer Seller & Card Optimizer

Search TCGPlayer for **Magic: The Gathering** and **Pokémon** cards with specific editions/versions. Find sellers who carry **all** cards in your list — ranked by cheapest total bundle price.

---

## Quick Start

### 1. Install dependencies
```bash
pip install playwright
playwright install chromium
```

### 2. Scrape a card combination
```bash
# Find sellers with BOTH an Unlimited Tropical Island AND an Alpha Black Lotus
python scraper.py \
  --cards "Tropical Island:Unlimited" "Black Lotus:Alpha" \
  --game mtg \
  --output combo.json

# Pokémon example
python scraper.py \
  --cards "Charizard:Base Set 1st Edition" "Blastoise:Base Set Shadowless" \
  --game pokemon \
  --output bundle.json

# Single card, any edition
python scraper.py --cards "Lightning Bolt" --game mtg --output bolt.json
```

### 3. Open the UI
Double-click **`index.html`** in your browser, then use **"Load saved results"** to load your `.json` file.

---

## Web UI Features

| Tab | What it shows |
|-----|---------------|
| **Bundles** | Sellers who have ALL cards you searched for, ranked by total bundle price (cheapest first) |
| **Cards** | All matching card listings from search results |
| **All Listings** | Every seller listing scraped — filterable by card |

- **Edition dropdown** — pick from full MTG or Pokémon set lists
- **Custom edition override** — type any version/printing freely
- **Multi-card slots** — add as many cards as you want; only sellers with all of them appear in Bundles
- **Export** — download results as CSV or JSON

---

## Scraper Options

| Flag | Default | Description |
|------|---------|-------------|
| `--cards` | *(required)* | One or more `"Name:Edition"` pairs |
| `--game` | *(required)* | `pokemon` or `mtg` |
| `--max-cards` | `5` | Search results per card |
| `--max-sellers` | `30` | Seller listings per card (higher = better bundle matching) |
| `--output` | `data.json` | Output file |
| `--no-sellers` | off | Skip seller step (just prices) |
| `--visible` | off | Show browser window |

---

## Notes
- Uses **Playwright** (headless Chromium) — required because TCGPlayer is JavaScript-rendered.
- Increase `--max-sellers` to improve bundle match rate (more sellers scraped = more overlap found).
- For personal/research use. See [TCGPlayer's ToS](https://help.tcgplayer.com/hc/en-us/articles/221672947).
