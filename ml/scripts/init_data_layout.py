"""Phase 2 / Step 1: create the TRINETRA data folder layout.

Works the same on Windows, macOS, Linux and Google Colab.

Usage (from the repo root):
    python ml/scripts/init_data_layout.py                  # local: <repo>/ml/data
    python ml/scripts/init_data_layout.py --root /content/drive/MyDrive/trinetra_data   # Colab / Drive
"""
import argparse
from pathlib import Path

LAYOUT = [
    "raw/imd_best_track",   # IMD RSMC best-track files exactly as downloaded
    "raw/ibtracs",          # NOAA IBTrACS (backup / cross-check for IMD tracks)
    "raw/mosdac/insat3d",   # INSAT-3D / 3DR imagery (large -> keep on Drive)
    "raw/mosdac/oscat",     # OSCAT scatterometer winds
    "raw/era5",             # ERA5 reanalysis NetCDF (large -> keep on Drive)
    "interim",              # cleaned / aligned data (Phase 3 will fill this)
    "processed",            # final model-ready tensors / tables
]


def main() -> None:
    default_root = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=default_root)
    root = parser.parse_args().root

    for sub in LAYOUT:
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
        print("ok  ", d)
    print(f"\nData layout ready under: {root}")


if __name__ == "__main__":
    main()
