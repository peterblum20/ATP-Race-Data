import csv
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://www.tennis24.com/rankings/wta-race/"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

def clean_name(name: str) -> str:
    # "Knutson Gabriela" etc — no country abbreviations here; those are in a separate cell
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name

def clean_int(s: str):
    s = (s or "").strip().replace(",", "")
    if not s or not re.fullmatch(r"\d+", s):
        return None
    return int(s)

def try_accept_cookies(page):
    # Tennis24 uses OneTrust (present in your debug HTML) :contentReference[oaicite:2]{index=2}
    for sel in [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        "button:has-text('I Agree')",
        "button:has-text('Agree')",
        "button:has-text('OK')",
    ]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=1500)
                page.wait_for_timeout(700)
                return True
        except Exception:
            pass
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try_accept_cookies(page)

        # Wait for table rows to exist (your HTML clearly contains rankingTable__row) :contentReference[oaicite:3]{index=3}
        page.wait_for_selector(".rankingTable__row", timeout=60000)

        # Click "Show more" until we have enough rows or it stops increasing
        # Your HTML shows the button text and structure. :contentReference[oaicite:4]{index=4}
        max_clicks = 50  # safety
        for _ in range(max_clicks):
            row_count = page.locator(".rankingTable__row").count()
            # includes header row; we’ll handle that when parsing
            if row_count >= (LIMIT + 1):
                break

            show_more = page.locator('button[data-testid="wcl-buttonLink"]', has_text="Show more")
            if show_more.count() == 0:
                break

            # Click and wait for more rows (count increases)
            try:
                show_more.first.click(timeout=5000)
            except PWTimeoutError:
                break

            # Wait for loading overlay to finish (in your HTML it says "Loading.") :contentReference[oaicite:5]{index=5}
            # Don’t hard-fail if it lingers; just give it time.
            page.wait_for_timeout(1200)

            # If row count doesn’t increase after a click, stop
            new_count = page.locator(".rankingTable__row").count()
            if new_count <= row_count:
                break

        # Parse rows
        rows = [["Player", "Points"]]
        row_locs = page.locator(".rankingTable__row")

        # Skip header row by requiring a player link
        n = row_locs.count()
        seen = set()

        for i in range(n):
            r = row_locs.nth(i)

            # Player anchor
            a = r.locator("a.rankingTable__href")
            if a.count() == 0:
                continue

            name = clean_name(a.first.inner_text().strip())

            # Points cell (bold, center, points) :contentReference[oaicite:6]{index=6}
            pts_text = r.locator(".rankingTable__cell--points").first.inner_text().strip()
            pts = clean_int(pts_text)
            if not name or pts is None:
                continue

            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            rows.append([name, pts])
            if len(rows) - 1 >= LIMIT:
                break

        browser.close()

    if len(rows) <= 1:
        raise RuntimeError("Scrape returned 0 rows (table present but parsing failed).")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    print(f"Wrote {len(rows)-1} rows to {OUT_FILE}")

if __name__ == "__main__":
    main()



