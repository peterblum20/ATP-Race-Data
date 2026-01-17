import csv
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.atptour.com/en/rankings/singles-race-to-turin"
OUT_FILE = "atp_race_top500.csv"

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

data = []

# The Race page is a real table; rows are in tbody/tr.
for row in soup.select("table tbody tr"):
    tds = row.find_all("td")
    if len(tds) < 2:
        continue

    # Player name is usually in the 2nd cell
    name = tds[1].get_text(" ", strip=True)

    # "Live Points" cell can contain multiple numbers like: "295 +250 - 295"
    # So we extract the FIRST integer we see.
    row_text = row.get_text(" ", strip=True)
    nums = re.findall(r"\b\d{1,5}\b", row_text)

    # Heuristic: live points is typically the first "standalone" number after the header fields;
    # in practice, taking the first number from the points cell works if we read that cell directly.
    # But because markup can shift, we fall back to scanning the row.
    points = None
    # Try last cell first (often contains live points + deltas) :contentReference[oaicite:1]{index=1}
    if len(tds) >= 3:
        last_cell = tds[-1].get_text(" ", strip=True)
        m = re.search(r"\b(\d{1,5})\b", last_cell)
        if m:
            points = int(m.group(1))

    # Fallback: any number in the row
    if points is None and nums:
        points = int(nums[0])

    if name and points is not None:
        data.append([name, points])

# Keep top 500
data = data[:500]

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Player", "Points"])
    w.writerows(data)

print(f"Wrote {len(data)} rows to {OUT_FILE}")



