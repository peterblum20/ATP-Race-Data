import csv
import requests
from bs4 import BeautifulSoup

URL = "https://www.atptour.com/en/rankings/singles-race-to-turin"
OUT_FILE = "atp_race_top500.csv"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

resp = requests.get(URL, headers=headers, timeout=30)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

data = []

# Each player row is in a <tr> with data attributes
for row in soup.select("table tbody tr"):
    cols = row.find_all("td")
    if len(cols) < 6:
        continue

    name = cols[1].get_text(strip=True)
    points = cols[-1].get_text(strip=True)

    if name and points.isdigit():
        data.append([name, points])

# Keep top 500
data = data[:500]

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Player", "Points"])
    writer.writerows(data)

print(f"Wrote {len(data)} rows")

