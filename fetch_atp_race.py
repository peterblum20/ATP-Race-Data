import csv
import re
import requests
from bs4 import BeautifulSoup

OUT_FILE = "atp_race_top500.csv"
BASE = "https://www.atptour.com/en/rankings/singles-race-to-turin"

RANGES = [(1,100), (101,200), (201,300), (301,400), (401,500)]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atptour.com/",
})

def first_int(s: str):
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"\b(\d{1,5})\b", s)
    return int(m.group(1)) if m else None

rows = [["Player", "Points"]]
seen = set()

for lo, hi in RANGES:
    url = f"{BASE}?countryCode=all&rankRange={lo}-{hi}"
    resp = session.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for tr in soup.select("table tbody tr"):
        tds = tr.find_all("td")
        # Expected columns: Live Rank | Player | Age | Current Tournament | Live Points | +/- | Next/Max
        if len(tds) < 5:
            continue

        raw_player = tds[1].get_text(" ", strip=True)

# Remove leading rank / change markers like "1 ", "-3 ", "+2 "
player = re.sub(r"^[+-]?\d+\s+", "", raw_player)

# Normalize whitespace
player = re.sub(r"\s+", " ", player).strip()

        pts_text = tds[4].get_text(" ", strip=True)
        pts = first_int(pts_text)

        if not player or pts is None:
            continue

        key = (player, pts)
        if key in seen:
            continue
        seen.add(key)
        rows.append([player, pts])

# Ensure exactly top 500
rows = rows[:501]

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerows(rows)

print(f"Wrote {len(rows)-1} rows to {OUT_FILE}")




