import csv
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://www.tennis24.com/rankings/wta-race/"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

DEBUG_HTML = Path("tennis24_debug.html")
DEBUG_PNG = Path("tennis24_debug.png")

def clean_name(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s

def dump_debug(page, note: str):
    print(f"[DEBUG] {note}")
    try:
        html = page.content()
        DEBUG_HTML.write_text(html, encoding="utf-8")
        page.screenshot(path=str(DEBUG_PNG), full_page=True)
        print(f"[DEBUG] Wrote {DEBUG_HTML} ({len(html)} chars) and {DEBUG_PNG}")
    except Exception as e:
        print(f"[DEBUG] Failed to write debug files: {e}")

def try_click_any(page):
    # Common consent frameworks/buttons across Flashscore/Tennis24 properties
    selectors = [
        "button:has-text('Accept')",
        "button:has-text('I Agree')",
        "button:has-text('Agree')",
        "button:has-text('Accept all')",
        "#onetrust-accept-btn-handler",
        "button#didomi-notice-agree-button",
        "button:has-text('OK')",
        "button:has-text('Got it')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=1500)
                page.wait_for_timeout(800)
                return True
        except Exception:
            pass
    return False

def main():
    rows_out = [["Player", "Points"]]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        print("[DEBUG] URL:", page.url)
        print("[DEBUG] Title:", page.title())

        # Try to clear consent overlays
        try_click_any(page)

        # Wait a bit for JS to fetch rankings
        page.wait_for_timeout(2500)

        # If the page is still just "Loading...", give it more time (raw HTML shows Loading) :contentReference[oaicite:1]{index=1}
        try:
            page.wait_for_function(
                "() => document.body && !document.body.innerText.includes('Loading...')",
                timeout=45000
            )
        except PWTimeoutError:
            # Still loading; dump debug and fail
            dump_debug(page, "Timed out waiting for Loading... to disappear.")
            raise RuntimeError("Tennis24 still showing 'Loading...' after 45s (likely blocked or stuck).")

        # Try again after loading finishes
        try_click_any(page)
        page.wait_for_timeout(1500)

        # Now attempt to detect ANY rankings rows.
        # Instead of relying on class names, look for text patterns like "Rankings" + many numeric rows.
        body_text = page.locator("body").inner_text(timeout=5000)
        digits = len(re.findall(r"\b\d{1,4}\b", body_text))
        print("[DEBUG] Digit-token count in body:", digits)

        # Pull candidate “row lines” from the page text.
        # On Tennis24 race rankings, each entry typically includes rank, player name, country, points.
        lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
        candidates = []
        for ln in lines:
            # Heuristic: line containing a rank and points somewhere
            if re.search(r"\b\d{1,4}\b", ln) and re.search(r"\b\d{2,7}\b", ln) and re.search(r"[A-Za-z]", ln):
                candidates.append(ln)

        print("[DEBUG] Candidate line count:", len(candidates))
        if len(candidates) < 20:
            dump_debug(page, "Not enough candidate ranking lines found in body text.")
            raise RuntimeError("Scrape returned 0 rows from Tennis24 (no ranking-like text detected).")

        # Parse from candidate lines.
        # We’ll take: player name = longest letter chunk; points = last integer in the line.
        seen = set()
        for ln in candidates:
            nums = re.findall(r"\b\d{1,7}\b", ln.replace(",", ""))
            if not nums:
                continue
            pts = int(nums[-1])

            # Pick the most name-like phrase: 2–5 word sequence containing letters
            name_phrases = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'’\-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’\-]+){1,4}", ln)
            if not name_phrases:
                continue
            name = clean_name(max(name_phrases, key=len))

            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            rows_out.append([name, pts])
            if len(rows_out) - 1 >= LIMIT:
                break

        browser.close()

    if len(rows_out) <= 1:
        raise RuntimeError("Parsed 0 rows from Tennis24 after candidate extraction.")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows_out)

    print(f"Wrote {len(rows_out)-1} rows to {OUT_FILE}")

if __name__ == "__main__":
    main()


