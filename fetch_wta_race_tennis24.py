import csv
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# Prefer LIVE; fall back to non-live if needed
URLS = [
    "https://www.tennis24.com/rankings/wta-race-live/",
    "https://www.tennis24.com/rankings/wta-race/",
]

OUT_FILE = "wta_race_top500.csv"
TARGET = 500          # try for 500
MIN_ACCEPTABLE = 300  # you said 300 is acceptable

def flip_last_first(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    parts = name.split(" ")
    if len(parts) >= 2:
        # "Paquet Chloe" -> "Chloe Paquet"
        return parts[-1] + " " + " ".join(parts[:-1])
    return name

def clean_int(s: str):
    s = (s or "").strip().replace(",", "")
    return int(s) if s.isdigit() else None

def try_accept_cookies(page):
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
                page.wait_for_timeout(600)
                return True
        except Exception:
            pass
    return False

def load_page_with_rows(page) -> str:
    last_err = None
    for url in URLS:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try_accept_cookies(page)
            page.wait_for_selector(".rankingTable__row", timeout=60000)
            return url
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Could not load Tennis24 rankings rows from any URL. Last error: {last_err}")

def click_show_more_until(page, want_rows: int) -> int:
    row_loc = page.locator(".rankingTable__row")

    # Keep clicking until we have enough rows or no longer increasing
    for _ in range(60):  # safety cap
        current = row_loc.count()
        if current >= want_rows:
            return current

        btn = page.locator('button[data-testid="wcl-buttonLink"]', has_text=re.compile("Show more", re.I))
        if btn.count() == 0:
            return current

        # Make sure it’s on-screen (important in headless)
        try:
            btn.first.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass

        try:
            btn.first.click(timeout=10000)
        except PWTimeoutError:
            return current

        # Wait until row count increases (or timeout)
        try:
            page.wait_for_function(
                "(prev) => document.querySelectorAll('.rankingTable__row').length > prev",
                arg=current,
                timeout=15000,
            )
        except PWTimeoutError:
            # Didn’t increase -> stop
            return row_loc.count()

    return row_loc.count()

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

        used_url = load_page_with_rows(page)
        print(f"Using Tennis24 URL: {used_url}")

        # Try to expand up to TARGET (+1 for header-ish row)
        final_count = click_show_more_until(page, TARGET + 1)
        print(f"Row count after expansion: {final_count}")

        rows = [["Player", "Points"]]
        seen = set()

        row_locs = page.locator(".rankingTable__row")
        n = row_locs.count()

        for i in range(n):
            r = row_locs.nth(i)

            a = r.locator("a.rankingTable__href")
            if a.count() == 0:
                continue

            raw_name = a.first.inner_text().strip()
            name = flip_last_first(raw_name)

            pts_text = r.locator(".rankingTable__cell--points").first.inner_text().strip()
            pts = clean_int(pts_text)

            if not name or pts is None:
                continue

            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            rows.append([name, pts])
            if len(rows) - 1 >= TARGET:
                break

        browser.close()

    wrote = len(rows) - 1
    if wrote < MIN_ACCEPTABLE:
        raise RuntimeError(f"Only scraped {wrote} rows (expected at least {MIN_ACCEPTABLE}).")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    print(f"Wrote {wrote} rows to {OUT_FILE}")

if __name__ == "__main__":
    main()



