import csv
import re
import sys
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.wtatennis.com/rankings/race-singles"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

# 1-50, 51-100, ... 451-500
RANGES = [(i, i + 49) for i in range(1, 501, 50)]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wtatennis.com/",
}

COUNTRY_RE = re.compile(r"^[A-Z]{3}$")
INT_RE = re.compile(r"^\d{1,7}$")
POINTS_RE = re.compile(r"^\d{1,3}(?:,\d{3})*$")  # allows "10,990"

def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    # remove trailing " CAN" style if present
    name = re.sub(r"\s+[A-Z]{3}$", "", name).strip()
    return name

def parse_players_points(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tokens = list(soup.stripped_strings)

    out = []

    # Find each player "card" by locating "View Profile"
    for i, tok in enumerate(tokens):
        if tok != "View Profile":
            continue

        # Look backwards in a reasonable window for:
        # Name, CountryCode, Age, Tournaments, Points (in that order) :contentReference[oaicite:2]{index=2}
        window = tokens[max(0, i - 40): i]  # preceding tokens

        # Find points: last numeric token before "View Profile"
        pts_idx = None
        for j in range(len(window) - 1, -1, -1):
            t = window[j].replace(",", "")
            if INT_RE.match(t):  # points / age / tournaments are all ints; we'll disambiguate by structure
                pts_idx = j
                break
        if pts_idx is None:
            continue

        # Now we expect: CountryCode, Age, Tournaments, Points at the tail
        # So points is window[pts_idx], tournaments is window[pts_idx-1], age is window[pts_idx-2]
        if pts_idx < 2:
            continue

        pts_raw = window[pts_idx]
        trn_raw = window[pts_idx - 1]
        age_raw = window[pts_idx - 2]

        # Ensure these are ints
        if not (INT_RE.match(pts_raw.replace(",", "")) and INT_RE.match(trn_raw) and INT_RE.match(age_raw)):
            continue

        # Country code should be just before age (often) or a few tokens before; search backwards for 3-letter code
        ctry_idx = None
        for j in range(pts_idx - 3, max(-1, pts_idx - 10), -1):
            if j >= 0 and COUNTRY_RE.match(window[j]):
                ctry_idx = j
                break
        if ctry_idx is None:
            continue

        # Name is typically right before the country code token
        if ctry_idx == 0:
            continue
        name_raw = window[ctry_idx - 1]

        # Filter out obvious non-name junk
        if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name_raw):
            continue

        name = clean_name(name_raw)
        points = int(pts_raw.replace(",", ""))

        out.append((name, points))

    # De-dupe while preserving order
    seen = set()
    deduped = []
    for name, points in out:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((name, points))

    return deduped

def main():
    rows = [["Player", "Points"]]
    seen_names = set()

    for lo, hi in RANGES:
        url = f"{BASE_URL}?rankRange={lo}-{hi}"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        print(f"WTA HTTP {resp.status_code}, length {len(resp.text)} for {lo}-{hi}")
        resp.raise_for_status()

        parsed = parse_players_points(resp.text)

        for name, pts in parsed:
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            rows.append([name, pts])
            if len(rows) - 1 >= LIMIT:
                break

        if len(rows) - 1 >= LIMIT:
            break

    if len(rows) <= 1:
        raise RuntimeError("Scrape returned 0 rows. Page structure or parsing assumptions changed.")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    print(f"Wrote {len(rows)-1} rows to {OUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise




