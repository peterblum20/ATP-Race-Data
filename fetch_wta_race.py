import csv
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.wtatennis.com/rankings/race-singles"
OUT_FILE = "wta_race_top500.csv"
LIMIT = 500

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

resp = session.get(URL, timeout=30, allow_redirects=True)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

# Try to locate a real HTML table first (best case)
table = soup.select_one("table")
if not table:
    raise RuntimeError("Could not find a <table> on the WTA race page.")

# Map columns by header text (robust to column order changes)
ths = table.select("thead th")
headers = [norm(th.get_text(" ", strip=True)) for th in ths]

def find_col(possible_names):
    for i, h in enumerate(headers):
        for name in possible_names:
            if name in h:
                return i
    return None

player_idx = find_col(["player"])
points_idx = find_col(["points"])

if player_idx is None or points_idx is None:
    raise RuntimeError(f"Could not locate Player/Points columns. Headers seen: {headers}")

rows_out = [["Player", "Points"]]

for tr in table.select("tbody tr"):
    tds = tr.find_all("td")
    if len(tds) <= max(player_idx, points_idx):
        continue

    raw_player = tds[player_idx].get_text(" ", strip=True)
    # Remove leading movement tokens like "+2 " or "-5 " if they appear
    player = re.sub(r"^[+-]?\d+\s+", "", raw_player)
    player = re.sub(r"\s+", " ", player).strip()

    pts_text = tds[points_idx].get_text(" ", strip=True)
    pts = first_int(pts_text)

    if player and (pts is not None):
        rows_out.append([player, pts])

    if len(rows_out) - 1 >= LIMIT:
        break

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerows(rows_out)

print(f"Wrote {len(rows_out)-1} rows to {OUT_FILE}")
