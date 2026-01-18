import re
import csv
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.wtatennis.com/rankings/race-singles"
OUTFILE = "wta_race_top500.csv"

# Some sites behave better with a real browser UA
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()

    # Remove trailing 3-letter country code (e.g., "Victoria Mboko CAN")
    name = re.sub(r"\s+[A-Z]{3}$", "", name).strip()

    return name

def parse_rows(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # This selector may differ depending on your existing script;
    # keep whatever you already have that correctly finds the rows.
    # Below is a common approach: find all "Rank" rows in the rankings table.
    rows = []

    # Example: find the section containing the "Rank Player ... Points" header, then iterate player blocks
    # If your current script already extracts Player + Points for top 50, reuse that logic here.
    for block in soup.select("[data-testid='rankings-table'] tr"):
        cols = [c.get_text(" ", strip=True) for c in block.select("td")]
        if not cols:
            continue

        # Heuristic: last column is points, player name is somewhere in the middle
        # You should map this to your known-good extraction logic.
        player = None
        points = None

        # Try to find a numeric "Points" field
        for c in reversed(cols):
            if re.fullmatch(r"[0-9,]+", c):
                points = c.replace(",", "")
                break

        # Try to find the player name: longest non-numeric cell that isn't a country code
        candidates = [c for c in cols if not re.fullmatch(r"[0-9,]+", c)]
        if candidates:
            # Often the player name is the longest text cell
            player = max(candidates, key=len)

        if player and points:
            player = clean_name(player)
            rows.append((player, int(points)))

    # Deduplicate while preserving order
    seen = set()
    out = []
    for p, pts in rows:
        if p not in seen:
            seen.add(p)
            out.append((p, pts))
    return out

def fetch_range(lo: int, hi: int) -> str:
    # Many WTA pages accept rankRange like "51-100"
    params = {"rankRange": f"{lo}-{hi}"}
    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def main():
    all_rows = []
    for lo in range(1, 501, 50):
        hi = lo + 49
        html = fetch_range(lo, hi)
        rows = parse_rows(html)
        all_rows.extend(rows)

    # Final dedupe, then take top 500
    seen = set()
    final = []
    for p, pts in all_rows:
        if p not in seen:
            seen.add(p)
            final.append((p, pts))
        if len(final) >= 500:
            break

    with open(OUTFILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Player", "Points"])
        w.writerows(final)

    print(f"Wrote {len(final)} rows to {OUTFILE}")

if __name__ == "__main__":
    main()


