"""Phase 2 / Step 6: inventory + sanity checks of everything under <root>/raw.

Checks
  1. IMD workbook still matches the SHA-256 recorded in SOURCE.txt.
  2. File counts / sizes per folder  -> <root>/raw/INVENTORY.csv
  3. BEST EFFORT coverage: if INSAT file names contain a timestamp such as
     05MAY2021_0300 (my understanding of the L1B naming; check against your real
     files), count files inside each storm's order window versus the ~2 scans/hour
     we expect. If names do not match, it says so and skips this check.

Usage:
    python ml/scripts/verify_raw_data.py
    python ml/scripts/verify_raw_data.py --root /content/drive/MyDrive/trinetra_data
"""
import argparse
import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path

STAMP = re.compile(r"(\d{2})([A-Z]{3})(\d{4})_(\d{4})")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def file_time(name: str):
    m = STAMP.search(name.upper())
    if not m:
        return None
    try:
        return datetime.strptime("".join(m.groups()), "%d%b%Y%H%M")
    except ValueError:
        return None


def main() -> None:
    default_root = Path(__file__).resolve().parents[1] / "data"
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=default_root)
    root = ap.parse_args().root
    raw = root / "raw"

    # 1. IMD hash
    src = raw / "imd_best_track" / "SOURCE.txt"
    if src.exists():
        info = dict(l.split(": ", 1) for l in src.read_text(encoding="utf-8").splitlines() if ": " in l)
        f = raw / "imd_best_track" / info["file"]
        ok = f.exists() and sha256(f) == info["sha256"]
        print(f"IMD workbook {'OK (hash matches SOURCE.txt)' if ok else 'MISSING or CHANGED'}: {f.name}")
    else:
        print("IMD workbook: no SOURCE.txt yet (run Step 2)")

    # 2. inventory
    rows = []
    for d in sorted(p for p in raw.rglob("*") if p.is_dir()):
        files = [p for p in d.iterdir() if p.is_file() and p.name != ".gitkeep"]
        if files:
            rows.append((str(d.relative_to(raw)), len(files), sum(p.stat().st_size for p in files)))
    with open(raw / "INVENTORY.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["folder", "n_files", "bytes"])
        w.writerows(rows)
    print("\nfolder                          files      size")
    for fol, n, b in rows:
        print(f"{fol:30s} {n:6d} {b/1e6:9.1f} MB")
    if not rows:
        print("(no raw data files yet)")

    # 3. coverage
    win_csv = root / "interim" / "mosdac_order_windows.csv"
    ins = raw / "mosdac" / "insat3d"
    if not win_csv.exists() or not ins.exists():
        return
    times = [t for p in ins.rglob("*") if p.is_file() for t in [file_time(p.name)] if t]
    if not times:
        print("\ncoverage: no timestamp found in INSAT file names; skipped (send me 5 file names).")
        return
    print(f"\ncoverage (file names parsed: {len(times)})")
    with open(win_csv, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            a = datetime.fromisoformat(r["window_start"])
            b = datetime.fromisoformat(r["window_end"])
            n = sum(a <= t <= b for t in times)
            expect = (b - a).total_seconds() / 1800
            print(f"  {r['storm_id']} {r['name'] or '-':10s} {n:5d} / ~{expect:.0f}  ({100*n/expect:.0f}%)")


if __name__ == "__main__":
    main()
