import requests
from bs4 import BeautifulSoup
import csv

URL = "https://live-tennis.eu/en/atp-race"
OUT_FILE = "atp_race_top500.csv"

headers = {
    "User-Agent": "Mozilla/5.0"
}

resp = requests.get(URL, headers=headers, timeout=30)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

rows = soup.select("table tr")

data = []
for row in rows:
    cols = [c.get_text(strip=True) for c in row.find_all("td")]
    if len(cols) >= 5 and cols[0].isdigit() and cols[4].isdigit():
        data.append([cols[1], cols[4]])

data = data[:500]

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Player", "Points"])
    writer.writerows(data)
