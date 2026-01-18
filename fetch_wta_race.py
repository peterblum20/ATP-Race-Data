# fetch_wta_race.py
import csv
import re
import sys
import requests
from bs4 import BeautifulSoup

URL = "https://www.wtatennis.com/rankings/race-singles"
OUT = "wta_race_top500.csv"
MAX_ROWS = 500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

TRAILING_COUNTRY = re.compile(r"\s+[A-Z]{3}$")  # e.g., "Victoria Mboko CAN" -> "Victoria Mboko"

def clean_name(name: str) -> str:
    name = name.strip()
    name = TRAILING_COUNTRY.sub("", name).strip()
    # remove stray digits (just in case)
    name = re.sub(r"\d+", "", name).strip()
    # collapse double spaces
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name

def main():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Strategy:
    # The WTA race page is rendered as repeated "player cards/rows".
    # We avoid brittle classnames by scanning for player/profile links and nearby "Points" values.

    # 1) Find all "View Profile" links (present per player row on the page). :contentReference[oaicite:1]{index=1}
    profile_links = soup.find_all("a", string=lambda s: isinstance(s, str) and "View Profile" in s)

    rows = []
    for a in profile_links:
        # walk up to a container that holds the player block
        container = a
        for _ in range(6):
            if container is None:
                break
            container = container.parent
            if container and container.get_text(" ", strip=True).count("View Profile"):
                break

        if not container:
            continue

        text = container.get_text(" ", strip=True)

        # Heuristic parse:
        # The block generally contains: Rank, movement, Name, country, age, tournaments played, points
        # We'll pull the first plausible "Name" (sequence of words) and last integer as points.
        nums = re.findall(r"\b\d+\b", text)
        if not nums:
            continue
        points = int(nums[-1])

        # Try to find the name by looking for a line near the link; best guess is the longest alpha chunk.
        # This is intentionally tolerant of minor page markup changes.
        candidates = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’-]+){1,4}", text)
        if not candidates:
            continue

        # Pick the “most name-like” candidate (longest that isn't generic UI text)
        bad = {"Ranking History", "Singles Form", "Latest Matches", "No recent matches available", "View Profile"}
        candidates = [c for c in candidates if c not in bad and "WTA" not in c and "Race" not in c]
        if not candidates:
            continue

        name = clean_name(max(candidates, key=len))

        if name and points >= 0:
            rows.append((name, points))

        if len(rows) >= MAX_ROWS:
            break

    # De-dup while preserving order (same player shouldn't repeat, but safety first)
    seen = set()
    deduped = []
    for name, points in rows:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((name, points))

    if len(deduped) == 0:
        raise RuntimeError("Scrape returned 0 rows (WTA page structure may have changed).")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Player", "Points"])
        w.writerows(deduped[:MAX_ROWS])

    print(f"Wrote {min(len(deduped), MAX_ROWS)} rows to {OUT}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()


