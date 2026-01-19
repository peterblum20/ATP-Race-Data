from datetime import datetime
from pathlib import Path
import shutil

# Files to archive
FILES = {
    "atp": "atp_race_top500.csv",
    "wta": "wta_race_top500.csv",
}

today = datetime.utcnow().strftime("%Y-%m-%d")

base = Path("archive")
base.mkdir(exist_ok=True)

for tour, filename in FILES.items():
    src = Path(filename)
    if not src.exists():
        print(f"Skipping {filename} (not found)")
        continue

    dest_dir = base / tour
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{tour}_race_{today}.csv"

    if dest.exists():
        print(f"Weekly snapshot already exists: {dest}")
        continue

    shutil.copy(src, dest)
    print(f"Archived {dest}")
