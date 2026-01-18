import csv
import re
from playwright.sync_api import sync_playwright

URL = "https://www.tennis24.com/rankings/wta-race/"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

def clean_name(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    # Just in case some country code gets glued onto the name:
    s = re.sub(r"\s+[A-Z]{3}$", "", s).strip()
    return s

def first_int(s: str):
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"\b(\d{1,7})\b", s)
    return int(m.group(1)) if m else None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # Try to dismiss cookie/consent overlays if they appear
    for txt in ["I Agree", "Accept", "AGREE", "Accept All"]:
        try:
            btn = page.get_by_role("button", name=txt)
            if btn.count() > 0:
                btn.first.click(timeout=1500)
                break
        except:
            pass

    # Tennis24/Flashscore-style pages usually render rows with class names containing "rankings__row"
    page.wait_for_selector('[class*="rankings__row"]', timeout=60000)

    # Click "Show more" until we have >= LIMIT rows (or no button exists)
    while True:
        row_count = page.locator('[class*="rankings__row"]').count()
        if row_count >= LIMIT:
            break

        # "Show more" is often a link/button at the bottom
        show_more = page.get_by_text("Show more", exact=False)
        if show_more.count() == 0:
            break

        try:
            show_more.first.click(timeout=5000)
            page.wait_for_timeout(1200)  # allow rows to append
        except:
            break

    # Extract rows in the browser context (more reliable than parsing HTML text)
    data = page.evaluate(
        """
        () => {
          const rows = Array.from(document.querySelectorAll('[class*="rankings__row"]'));
          return rows.map(r => r.innerText);
        }
        """
    )

    browser.close()

rows_out = [["Player", "Points"]]

for raw in data:
    # raw often looks like: "1. Bencic Belinda +14 Switzerland 554 2"
    # We'll pull player name = best non-numeric chunk, points = first reasonable integer near end
    parts = [p.strip() for p in re.split(r"\\n|\\t", raw) if p.strip()]
    flat = " ".join(parts)
    tokens = [t for t in re.split(r"\\s+", flat) if t]

    # Points: take the last integer-like token (common layout)
    pts = None
    for t in reversed(tokens):
        x = first_int(t)
        if x is not None:
            pts = x
            break
    if pts is None:
        continue

    # Name: remove obvious numeric / country-ish stuff and keep a plausible name span
    # Find the longest token span with letters.
    letter_tokens = [t for t in tokens if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", t)]
    if not letter_tokens:
        continue

    # Heuristic: name is usually the first 2–4 “word” tokens after the rank token.
    # We'll strip leading rank like "1." / "1"
    idx0 = 0
    if tokens and re.match(r"^\\d+\\.?$", tokens[0]):
        idx0 = 1

    # Build a candidate name from the next few tokens until we hit a clear non-name marker
    name_tokens = []
    for t in tokens[idx0:]:
        # Stop at movement markers or pure numbers
        if re.match(r"^[+-]\\d+$", t) or re.match(r"^\\d+$", t):
            break
        # Stop if it looks like a country name (can be multi-word, so we keep it simple)
        # We'll rely on "first chunk before numeric" most of the time.
        name_tokens.append(t)
        if len(name_tokens) >= 4:
            break

    player = clean_name(" ".join(name_tokens))
    if not player:
        continue

    rows_out.append([player, pts])
    if len(rows_out) - 1 >= LIMIT:
        break

# Fail loudly if we didn’t get anything (prevents “headers only” CSV)
if len(rows_out) <= 1:
    raise RuntimeError("Scrape returned 0 rows from Tennis24. Likely selector/cookie overlay changed.")

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows_out)

print(f"Wrote {len(rows_out)-1} rows to {OUT_FILE}")
