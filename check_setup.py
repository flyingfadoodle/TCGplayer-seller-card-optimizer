#!/usr/bin/env python3
"""
TCGPlayer Optimizer — Setup Checker
Run this first to verify everything is installed correctly.
"""
import sys
import subprocess

OK    = "  ✅"
FAIL  = "  ❌"
WARN  = "  ⚠️ "

print("\n" + "═"*52)
print("  TCGPlayer Optimizer — Setup Check")
print("═"*52)

errors = []

# Python version
major, minor = sys.version_info[:2]
if major >= 3 and minor >= 8:
    print(f"{OK}  Python {major}.{minor} (3.8+ required)")
else:
    print(f"{FAIL}  Python {major}.{minor} — need 3.8 or newer")
    print(f"       Download: https://www.python.org/downloads/")
    errors.append("python")

# Playwright library
try:
    import playwright
    print(f"{OK}  Playwright library installed")
except ImportError:
    print(f"{FAIL}  Playwright library not found")
    print(f"       Fix: pip install playwright")
    errors.append("playwright-lib")

# Playwright browser (chromium)
browser_ok = False
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
    print(f"{OK}  Chromium browser ready")
    browser_ok = True
except Exception as e:
    msg = str(e)
    if "Executable doesn't exist" in msg or "browserType.launch" in msg:
        print(f"{FAIL}  Chromium browser not installed")
        print(f"       Fix: playwright install chromium")
    else:
        print(f"{WARN}  Chromium check failed: {msg[:80]}")
    errors.append("chromium")

print("═"*52)

if not errors:
    print("  🎉  All good! You're ready to scrape.\n")
    print("  Try:")
    print('    python scraper.py --cards "Black Lotus:Alpha" --game mtg --output data.json\n')
else:
    print("  Run these commands to fix the issues above:\n")
    if "python" in errors:
        print("    1. Download Python 3.8+: https://www.python.org/downloads/")
    if "playwright-lib" in errors:
        print("    pip install playwright")
    if "chromium" in errors:
        print("    playwright install chromium")
    print()
