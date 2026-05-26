# TCGPlayer Seller & Card Optimizer

Search TCGPlayer for **Magic: The Gathering** and **Pokémon** cards, compare seller listings by price and condition, and export to CSV or JSON — all from a clean local web UI.

---

## Quick Start

### 1. Install dependencies
```bash
pip install playwright
playwright install chromium
```

### 2. Scrape a card
```bash
python scraper.py "Charizard" --game pokemon --output data.json
python scraper.py "Black Lotus" --game mtg --output lotus.json
```

### 3. Open the UI
Double-click **`index.html`** (or open it in your browser), then click **"Choose File"** and load the `.json` file the scraper produced.

That's it — you'll see all matching cards and their seller listings.

---

## Scraper Options

| Flag | Default | Description |
|------|---------|-------------|
| `--game` | *(required)* | `pokemon` or `mtg` |
| `--max-cards` | `10` | Max cards to pull from search results |
| `--max-sellers` | `10` | Max seller listings per card |
| `--output` | *(none)* | Save results as `.json` (load in UI) |
| `--no-sellers` | off | Skip seller step — much faster |
| `--visible` | off | Show the browser window (good for debugging) |

### Examples
```bash
# Fast price check — no seller details
python scraper.py "Pikachu" --game pokemon --no-sellers --output pikachu.json

# Deep dive — 20 cards, 25 sellers each
python scraper.py "Lightning Bolt" --game mtg --max-cards 20 --max-sellers 25 --output bolt.json

# Watch the browser scrape in real time
python scraper.py "Mewtwo" --game pokemon --visible
```

---

## Web UI Features

- 🃏 **Card grid** — click any card to filter sellers to just that card
- 💰 **Seller table** — price, condition badge, shipping, quantity
- 📤 **Export** — download results as CSV or JSON directly from the browser
- 🔗 **Direct links** — jump to any listing on TCGPlayer

---

## Notes

- TCGPlayer renders with JavaScript, so **Playwright** (headless Chromium) is required — regular `requests` won't work.
- Be respectful: don't run the scraper in rapid loops.
- If TCGPlayer updates their page layout, CSS selectors may need updating. Run with `--visible` to debug.
- This tool is for **personal/research use**. Review [TCGPlayer's Terms of Service](https://help.tcgplayer.com/hc/en-us/articles/221672947) before any commercial use.
