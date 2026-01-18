import csv
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.wtatennis.com/rankings/race-singles"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

# WTA page offers rank ranges (1-50, 51-100, ..., 451-500). :contentReference[oaicite:1]{index=1}
RANGES = [(1, 50), (51, 100), (101, 150), (151, 200), (201, 250),
          (251, 300), (301, 350), (351, 400), (401, 450), (451, 500)]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wtatennis.com/",
})

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def first_int(s: str):
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"\b(\d{1,7})\b", s)
    return int(m.group(1)) if m else None

def clean_player(raw: str) -> str:
    # remove leading movement tokens like "+2 " or "-5 "
    s = re.sub(r"^[+-]?\d+\s+", "", raw.strip())

    # remove trailing country code like " CAN" / " USA" / " GBR"
    s = re.sub(r"\s+[A-Z]{3}$", "", s).strip()

    # normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table")
    if not table:
        return []

    headers = [norm(th.get_text(" ", strip=True)) for th in table.select("thead th")]

    def find_col(possible_names):
        for i, h in enumerate(headers):
            for name in possible_names:
                if name in h:
                    return i
        return None

    player_idx = find_col(["player"])
    points_idx = find_col(["points"])

    if player_idx is None or points_idx is None:
        return []

    out = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) <= max(player_idx, points_idx):
            continue

        raw_player = tds[player_idx].get_text(" ", strip=True)
        player = clean_player(raw_player)

        pts_text = tds[points_idx].get_text(" ", strip=True)
        pts = first_int(pts_text)

        if player and pts is not None:
            out.append((player, pts))
    return out

rows = [["Player", "Points"]]
seen = set()

for lo, hi in RANGES:
    url = f"{BASE_URL}?rankRange={lo}-{hi}"
    resp = session.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    for player, pts in extract_from_html(resp.text):
        key = (player, pts)
        if key in seen:
            continue
        seen.add(key)
        rows.append([player, pts])
        if len(rows) - 1 >= LIMIT:
            break

    if len(rows) - 1 >= LIMIT:
        break

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)

print(f"Wrote {len(rows) - 1} rows to {OUT_FILE}")

