import csv
import re
from playwright.sync_api import sync_playwright

URL = "https://live-tennis.eu/en/wta-race"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

def clean_player(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    # live-tennis includes rank change / misc tokens sometimes; keep only the name portion.
    # Remove leading +/-digits tokens like "+3 " or "-2 "
    s = re.sub(r"^[+-]?\d+\s+", "", s)
    return s.strip()

def first_int(s: str):
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"\b(\d{1,7})\b", s)
    return int(m.group(1)) if m else None

rows = [["Player", "Points"]]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # If Cloudflare interstitial shows, give it a moment to pass
    page.wait_for_timeout(8000)

    # Wait for the rankings table to appear (live-tennis page shows a table with headers like "# Player ... Pts") :contentReference[oaicite:2]{index=2}
    page.wait_for_selector("table", timeout=60000)

    html = page.content()
    browser.close()

# Parse the HTML with regex/bs-like approach without adding bs4 dependency:
# We'll do a minimal parse by pulling rows and cells via regex—works fine for this table shape.
# (If you prefer bs4, we can use it too.)
import bs4
soup = bs4.BeautifulSoup(html, "html.parser")

table = soup.select_one("table")
if not table:
    raise RuntimeError("Could not find table on live-tennis WTA race page.")

for tr in table.select("tr"):
    tds = tr.find_all("td")
    if len(tds) < 5:
        continue

    # live-tennis columns: # | Player | Age | Ctry | Pts | ... :contentReference[oaicite:3]{index=3}
    player_raw = tds[1].get_text(" ", strip=True)
    pts_raw = tds[4].get_text(" ", strip=True)

    player = clean_player(player_raw)
    pts = first_int(pts_raw)

    if player and pts is not None:
        rows.append([player, pts])
        if len(rows) - 1 >= LIMIT:
            break

if len(rows) <= 1:
    raise RuntimeError("Scrape returned 0 rows (likely blocked by Cloudflare).")

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)

print(f"Wrote {len(rows)-1} rows to {OUT_FILE}")
