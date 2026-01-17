import csv
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.atptour.com/en/rankings/singles-race-to-turin"
OUT_FILE = "atp_race_top500.csv"
LIMIT = 500

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atptour.com/",
})

resp = session.get(URL, timeout=30, allow_redirects=True)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")
table = soup.select_one("table")
if not table:
    raise RuntimeError("Could not find a table on the page.")

# ---- 1) Find header columns ----
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

ths = table.select("thead th")
headers = [norm(th.get_text(" ", strip=True)) for th in ths]

# On ATP Race page, header includes "Player" and "Live Points" (sometimes just "Points"). :contentReference[oaicite:2]{index=2}
def find_col(possible_names):
    for i, h in enumerate(headers):
        for name in possible_names:
            if name in h:
                return i
    return None

player_idx = find_col(["player"])
points_idx = find_col(["live points", "points"])

if player_idx is None or points_idx is None:
    raise RuntimeError(f"Could not locate Player/Points columns. Headers seen: {headers}")

# ---- 2) Extract rows ----
rows_out = [["Player", "Points"]]
for tr in table.select("tbody tr"):
    tds = tr.find_all("td")
    if len(tds) <= max(player_idx, points_idx):
        continue

    # Player cell often has extra whitespace/icons; text extraction is fine.
    player = tds[player_idx].get_text(" ", strip=True)

    # Points cell can contain "295 +250 - 295" etc; take the first integer.
    pts_text = tds[points_idx].get_text(" ", strip=True).replace(",", "")
    m = re.search(r"\b(\d{1,5})\b", pts_text)
    if not (player and m):
        continue

    rows_out.append([player, int(m.group(1))])
    if len(rows_out) - 1 >= LIMIT:
        break

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(rows_out[0])
    w.writerows(rows_out[1:])

print(f"Wrote {len(rows_out)-1} rows to {OUT_FILE}")



