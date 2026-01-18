import csv
import re
from playwright.sync_api import sync_playwright

URL = "https://www.tennis24.com/rankings/wta-race/"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

def clean_name(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s

def parse_points_from_text(row_text: str):
    # row text often contains multiple numbers; points is usually the SECOND-to-last integer
    nums = re.findall(r"\b\d{1,7}\b", row_text.replace(",", ""))
    if len(nums) < 2:
        return None
    return int(nums[-2])

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # Wait until the page is no longer showing just "Loading..."
    page.wait_for_function(
        "() => document.body && !document.body.innerText.includes('Loading...')",
        timeout=60000
    )

    # Wait until player profile links exist (rankings are loaded)
    page.wait_for_selector('a[href*="/player/"]', state="attached", timeout=60000)

    # Try clicking "Show more" if it exists, to expand beyond the default set
    for _ in range(30):  # prevent infinite loops
        links_count = page.locator('a[href*="/player/"]').count()
        if links_count >= LIMIT:
            break
        show_more = page.get_by_text("Show more", exact=False)
        if show_more.count() == 0:
            break
        try:
            show_more.first.click(timeout=5000)
            page.wait_for_timeout(1200)
        except:
            break

    # Extract rows by anchoring on player links and reading their closest container text
    data = page.evaluate(
        """
        () => {
          const anchors = Array.from(document.querySelectorAll('a[href*="/player/"]'));
          const out = [];
          for (const a of anchors) {
            // Find a reasonable container for this player's row/card
            const row = a.closest('div, tr, li') || a.parentElement;
            if (!row) continue;
            const txt = (row.innerText || '').trim();
            if (txt.length < 10) continue;
            out.push({ name: a.textContent.trim(), rowText: txt });
          }
          return out;
        }
        """
    )

    browser.close()

rows_out = [["Player", "Points"]]
seen = set()

for item in data:
    name = clean_name(item.get("name", ""))
    row_text = item.get("rowText", "")

    if not name:
        continue

    pts = parse_points_from_text(row_text)
    if pts is None:
        continue

    key = name.lower()
    if key in seen:
        continue
    seen.add(key)

    rows_out.append([name, pts])
    if len(rows_out) - 1 >= LIMIT:
        break

if len(rows_out) <= 1:
    raise RuntimeError("Scrape returned 0 rows from Tennis24 (page structure or blocking).")

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows_out)

print(f"Wrote {len(rows_out)-1} rows to {OUT_FILE}")

