import csv
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.wtatennis.com/rankings/race-singles?rankRange=1-500"
OUT = Path("wta_race_top500.csv")


def clean_name(name: str) -> str:
    # Remove trailing country abbreviation if it somehow appears in the same token
    # e.g. "Victoria Mboko CAN" -> "Victoria Mboko"
    name = re.sub(r"\s+[A-Z]{3}$", "", name.strip())
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fetch_html(url: str) -> str:
    headers = {
        # A “real browser” UA helps a lot in GitHub Actions environments
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.wtatennis.com/rankings",
        "Connection": "keep-alive",
    }

    resp = requests.get(url, headers=headers, timeout=30)
    print(f"WTA HTTP {resp.status_code}, length {len(resp.text)}")

    # If the page is blocked / bot-checked, fail loudly with a useful snippet.
    if resp.status_code != 200:
        snippet = resp.text[:500].replace("\n", " ")
        raise RuntimeError(f"Non-200 response {resp.status_code}. Snippet: {snippet}")

    return resp.text


def parse_players_points(html: str):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    rows = []
    i = 0

    # Heuristic: each player block looks like:
    # "<rank>  <something>" then next line is player name,
    # later within a few lines we see "<age>  <tournaments>  <points>"
    rank_two_ints = re.compile(r"^\d{1,4}\s+\d{1,4}$")
    age_tourn_points = re.compile(r"^\d{1,2}\s+\d{1,3}\s+[\d,]{1,7}$")

    while i < len(lines):
        if rank_two_ints.match(lines[i]):
            # Candidate block start
            # Next non-empty line is usually the player name
            if i + 1 < len(lines):
                name = lines[i + 1]
                # Skip obvious non-name junk
                if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name):
                    i += 1
                    continue

                # Find points line within next ~15 lines
                pts = None
                for j in range(i + 1, min(i + 20, len(lines))):
                    if age_tourn_points.match(lines[j]):
                        # Points are last token
                        pts = lines[j].split()[-1].replace(",", "")
                        break

                if pts is not None:
                    rows.append((clean_name(name), int(pts)))
                    i += 2
                    continue

        i += 1

    # De-dup while keeping order (page text can repeat a few items)
    seen = set()
    deduped = []
    for name, pts in rows:
        key = (name, pts)
        if key not in seen:
            seen.add(key)
            deduped.append((name, pts))

    return deduped


def main():
    html = fetch_html(URL)
    rows = parse_players_points(html)

    if len(rows) == 0:
        # Print a hint for debugging if this ever happens again
        raise RuntimeError(
            "Scrape returned 0 rows. The response HTML likely changed or was blocked. "
            "Check the printed HTTP status/length in the Actions log."
        )

    # Keep only top 500 (just in case)
    rows = rows[:500]

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Player", "Points"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)



