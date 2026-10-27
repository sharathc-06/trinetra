"""Phase 2 / Step 4 (v2, written for the REAL IMD workbook layout).

The IMD workbook has ONE SHEET PER YEAR (1982-2026), header row on row 1-3,
no Year column, serial/name/date filled only on the first row of a storm / day,
times as '0300' / 300 / 0 / '1200  ', numbers stored as text, and free-text note
rows ("Weakened into low pressure area", "Crossed ... coast") mixed with data.

This script cleans all of that and writes (under <root>/interim/):
    imd_best_track_tidy.csv     one row per best-track fix
    storms.csv                  one row per storm
    mosdac_order_windows.csv    storms to order imagery for (start >= --imagery-start)
    parse_report.csv            per-sheet counts and warnings  -> READ THIS

Usage (repo root):
    python ml/scripts/build_storm_list.py
    python ml/scripts/build_storm_list.py --root /content/drive/MyDrive/trinetra_data
"""
import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

GRADE_ORDER = ["D", "DD", "CS", "SCS", "VSCS", "ESCS", "SUCS"]  # weakest -> strongest
DEFAULT_AOI = {"lat_min": 0, "lat_max": 30, "lon_min": 40, "lon_max": 100}
MISSING_TEXT = {"", "-", "--", "nan", "none", "null"}
DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"]


def norm(x) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def clean_text(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip()
    return t.mask(t.str.lower().isin(MISSING_TEXT))


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.strip(), errors="coerce")


def parse_date_value(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return pd.NaT
    if isinstance(v, (datetime, pd.Timestamp)):
        return pd.Timestamp(v).normalize()
    s = str(v).strip()
    for f in DATE_FORMATS:
        try:
            return pd.Timestamp(datetime.strptime(s, f))
        except ValueError:
            pass
    return pd.NaT


def parse_hhmm(v) -> float:
    """Minutes since midnight from 0300, 300, 0, '1200  ', '03:00', datetime.time. NaN if invalid."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return float("nan")
    if hasattr(v, "hour") and hasattr(v, "minute"):
        return v.hour * 60 + v.minute
    s = str(v).strip()
    if ":" in s:
        try:
            h, m = s.split(":")[:2]
            return int(h) * 60 + int(m)
        except ValueError:
            return float("nan")
    try:
        n = int(float(s))
    except ValueError:
        return float("nan")
    h, m = divmod(n, 100)
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else float("nan")


def grade_from_wind(w: float) -> str:
    """IMD classes from max sustained wind in knots (kept in its own column, never overwrites 'grade')."""
    if pd.isna(w):
        return ""
    for lim, g in [(17, "LP"), (28, "D"), (34, "DD"), (48, "CS"), (64, "SCS"), (90, "VSCS"), (120, "ESCS")]:
        if w < lim:
            return g
    return "SUCS"


def find_header(raw: pd.DataFrame):
    for i in range(min(10, len(raw))):
        cells = [norm(v) for v in raw.iloc[i].tolist()]
        if any(c.startswith("date") for c in cells) and any(c.startswith("lat") for c in cells):
            return i, cells
    return None, None


def map_columns(cells):
    rules = {
        "serial": lambda c: c.startswith("serial"),
        "basin": lambda c: "basin" in c or "origin" in c,
        "name": lambda c: c == "name",
        "date": lambda c: c.startswith("date"),
        "time": lambda c: c.startswith("time"),
        "lat": lambda c: c.startswith("lat"),
        "lon": lambda c: c.startswith("lon"),
        "ci": lambda c: c.startswith("ci"),
        "pressure": lambda c: c.startswith("estimatedcentral") or c.startswith("ecp"),
        "wind": lambda c: c.startswith("maximum") or "wind" in c,
        "pdrop": lambda c: c.startswith("pressuredrop"),
        "grade": lambda c: c.startswith("grade"),
    }
    idx = {}
    for key, fn in rules.items():
        for j, c in enumerate(cells):
            if fn(c) and j not in idx.values():
                idx[key] = j
                break
    for key, pos in [("serial", 0), ("basin", 1), ("name", 2)]:  # positional fallback (e.g. header typo)
        idx.setdefault(key, pos)
    return idx


def resolve_dates(vals, flags, sheet_year):
    """Repair explicit date cells of ONE storm run using continuity (Viterbi over 2-4 candidates per cell).

    Excel often read DD-MM-YYYY typed dates month-first, so a cell holding 7 June may really be 6 July.
    Only real datetime cells with day <= 12 can be swapped. Also fixes year typos (date year != sheet year).
    The sequence of dates inside a storm is almost always continuous, so we choose the candidates that keep it
    continuous. Small prior penalties: swap 0.5 day, year change 3 days. A storm whose cells are all consistently
    swapped (e.g. a single date) cannot be detected and is left as-is.
    Returns (fixed_dates, n_swapped, n_year_fixed)."""
    cands = []
    for v, is_dt in zip(vals, flags):
        c = [(v, 0.0, 0, 0)]
        if is_dt and v.day <= 12 and v.day != v.month:
            c.append((pd.Timestamp(year=v.year, month=v.day, day=v.month), 0.5, 1, 0))
        if sheet_year is not None:
            for t, pen, sw, _ in list(c):
                if t.year != sheet_year:
                    try:
                        c.append((t.replace(year=sheet_year), pen + 3.0, sw, 1))
                    except ValueError:
                        pass
        cands.append(c)
    cost = [[x[1] for x in cands[0]]]
    back = []
    for i in range(1, len(cands)):
        row, brow = [], []
        for t, pen, _, _ in cands[i]:
            best = None
            for j, (t0, _, _, _) in enumerate(cands[i - 1]):
                diff = (t - t0).days
                tot = cost[-1][j] + abs(diff) + (3.0 if diff < 0 else 0.0)
                if best is None or tot < best[0]:
                    best = (tot, j)
            row.append(best[0] + pen)
            brow.append(best[1])
        cost.append(row)
        back.append(brow)
    k = min(range(len(cost[-1])), key=lambda x: cost[-1][x])
    path = [k]
    for brow in reversed(back):
        k = brow[k]
        path.append(k)
    path.reverse()
    chosen = [cands[i][p] for i, p in enumerate(path)]
    return [c[0] for c in chosen], sum(c[2] for c in chosen), sum(c[3] for c in chosen)


def parse_sheet(raw: pd.DataFrame, sheet: str):
    rep = {"sheet": sheet, "raw_rows": len(raw), "kept": 0, "storms": 0, "blank_rows": 0, "note_rows": 0,
           "bad_time": 0, "dupes": 0, "out_of_range": 0, "day_rollover_fixed": 0,
           "dates_swapped": 0, "years_fixed": 0, "warnings": ""}
    warn = []
    hdr, cells = find_header(raw)
    if hdr is None:
        rep["warnings"] = "no header row found; sheet skipped"
        return None, rep, None
    idx = map_columns(cells)
    missing = [k for k in ["date", "time", "lat", "lon"] if k not in idx]
    if missing:
        rep["warnings"] = f"missing columns {missing}; sheet skipped"
        return None, rep, None

    body = raw.iloc[hdr + 1:]
    d = pd.DataFrame({k: body.iloc[:, j] for k, j in idx.items()})
    d["excel_row"] = body.index + 1                                  # row number as shown in Excel
    has_content = d.drop(columns="excel_row").notna().any(axis=1)    # content in the columns we use
    rep["blank_rows"] = int((~has_content).sum())
    d = d[has_content].copy()

    d["lat_raw"], d["lon_raw"] = d["lat"], d["lon"]
    d["lat"], d["lon"] = num(d["lat"]), num(d["lon"])
    is_fix = d["lat"].notna() & d["lon"].notna()
    notes = d[~is_fix]                                               # note rows: "Weakened into ...", "Crossed ..."
    rep["note_rows"] = len(notes)
    dropped = notes[["excel_row", "serial", "date", "time", "lat_raw", "lon_raw"]].copy()
    dropped.insert(0, "sheet", sheet)
    d = d[is_fix].copy()
    ok = d["lat"].between(-10, 50) & d["lon"].between(30, 125)
    rep["out_of_range"] = int((~ok).sum())
    d = d[ok].copy()
    if d.empty:
        rep["warnings"] = "no data rows"
        return None, rep, dropped

    d["serial"] = num(d["serial"]).ffill()
    if d["serial"].isna().any():
        warn.append(f"{int(d['serial'].isna().sum())} rows before first serial dropped")
        d = d[d["serial"].notna()].copy()
    d["serial"] = d["serial"].astype(int)
    # a "run" = consecutive rows with the same serial. The same serial can reappear in another part of the
    # sheet (separate block) - that is a different system, so it gets its own id (suffix r2, r3, ...).
    d["run"] = (d["serial"] != d["serial"].shift()).cumsum()
    runs = d[["serial", "run"]].drop_duplicates()
    runs["occ"] = runs.groupby("serial").cumcount() + 1
    d = d.merge(runs[["run", "occ"]], on="run", how="left").set_index(d.index)
    for k in ["name", "basin"]:                                       # per run: first non-empty value
        d[k] = clean_text(d[k])
        d[k] = d.groupby("run")[k].transform("first")
    d["name"] = d["name"].str.upper()
    d["basin"] = d["basin"].str.upper().str.replace(r"\s+", " ", regex=True).replace({"AS": "ARB"})

    # --- timestamps: date is often blank after the first fix of a day; time is HHMM
    d["date_is_dt"] = d["date"].map(lambda v: isinstance(v, (datetime, pd.Timestamp)))
    d["date_raw"] = d["date"].map(parse_date_value).astype("datetime64[ns]")
    minutes = d["time"].map(parse_hhmm)
    bad = minutes.isna()
    rep["bad_time"] = int(bad.sum())
    d, minutes = d[~bad].copy(), minutes[~bad]
    sheet_year = int(sheet) if str(sheet).isdigit() else None
    fixed_dates, n_sw, n_yf = d["date_raw"].copy(), 0, 0
    for _, grp in d.groupby("run", sort=False):
        ok_idx = grp.index[grp["date_raw"].notna()]
        if len(ok_idx):
            res, a, b = resolve_dates(list(d.loc[ok_idx, "date_raw"]), list(d.loc[ok_idx, "date_is_dt"]), sheet_year)
            fixed_dates.loc[ok_idx] = pd.Series(res, index=ok_idx).astype("datetime64[ns]")
            n_sw, n_yf = n_sw + a, n_yf + b
    d["date_raw"] = fixed_dates
    rep["dates_swapped"], rep["years_fixed"] = n_sw, n_yf
    dates, cur, prev, last_run, fixed = [], pd.NaT, None, None, 0
    for ser, dr, mn in zip(d["run"], d["date_raw"], minutes):
        if ser != last_run:
            prev, last_run = None, ser
        if pd.notna(dr):
            cur = dr
        elif pd.notna(cur) and prev is not None and mn < prev:        # time-of-day wrapped but date cell blank
            cur = cur + pd.Timedelta(days=1)
            fixed += 1
        dates.append(cur)
        prev = mn
    d["date"] = pd.Series(dates, index=d.index).astype("datetime64[ns]")
    nodate = d["date"].isna()
    rep["bad_time"] += int(nodate.sum())
    d, minutes = d[~nodate].copy(), minutes[~nodate]
    rep["day_rollover_fixed"] = fixed
    d["time"] = d["date"] + pd.to_timedelta(minutes, unit="m").astype("timedelta64[ns]")

    try:
        year = int(sheet)
        off = ~d["time"].dt.year.between(year - 1, year + 1)
        if off.any():
            warn.append(f"{int(off.sum())} rows with date far from sheet year dropped")
            d = d[~off].copy()
    except ValueError:
        year = int(d["time"].dt.year.mode().iloc[0])
        warn.append("sheet name is not a year; year taken from dates")

    for k in ["ci", "pressure", "wind", "pdrop"]:
        d[k] = num(d[k]) if k in d else float("nan")
    g = clean_text(d["grade"]).str.upper().str.replace(r"\s+", " ", regex=True) if "grade" in d else pd.Series(pd.NA, index=d.index)
    d["grade_raw"] = g
    d["over_land"] = g.str.startswith("D OVER", na=False)
    d["grade"] = g.mask(d["over_land"], "D")                        # "D OVER LAND" -> D, flagged in over_land
    if "grade" in idx and d["grade"].isna().mean() > 0.5:
        warn.append("grade column mostly empty (columns may be shifted)")
    d["grade_from_wind"] = d["wind"].map(grade_from_wind)
    d["storm_id"] = (f"{year}-" + d["serial"].astype(str).str.zfill(2)
                     + d["occ"].map(lambda o: "" if o == 1 else f"r{o}"))
    d["sheet_year"] = year
    d["provisional"] = (year == 2026)

    d = d.sort_values(["storm_id", "time"])
    before = len(d)
    d = d.drop_duplicates(subset=["storm_id", "time"], keep="first")
    rep["dupes"] = before - len(d)
    keep = ["storm_id", "sheet_year", "serial", "basin", "name", "time", "lat", "lon", "wind", "pressure",
            "pdrop", "ci", "grade", "grade_raw", "grade_from_wind", "over_land", "provisional", "excel_row"]
    d = d[keep].reset_index(drop=True)
    rep["kept"], rep["storms"], rep["warnings"] = len(d), d["storm_id"].nunique(), "; ".join(warn)
    return d, rep, dropped


def split_on_gaps(tidy: pd.DataFrame, max_gap_hours: float):
    """Split a storm into separate storms wherever consecutive fixes are > max_gap_hours apart.
    Real best-track fixes are 3-12 h apart, so a multi-day gap means merged storms or a date typo."""
    tidy = tidy.sort_values(["storm_id", "time"]).reset_index(drop=True)
    gap = tidy.groupby("storm_id")["time"].diff().dt.total_seconds() / 3600
    new_seg = (gap > max_gap_hours).fillna(False)
    seg = new_seg.groupby(tidy["storm_id"]).cumsum()
    log = tidy.loc[new_seg, ["storm_id", "name", "time", "excel_row"]].copy()
    log["gap_hours"] = gap[new_seg].round(1)
    log["sheet_year"] = tidy.loc[new_seg, "sheet_year"]
    tidy["parent_id"] = tidy["storm_id"]
    tidy["storm_id"] = tidy["storm_id"].where(seg == 0, tidy["storm_id"] + "." + (seg + 1).astype(str))
    return tidy, log


def summarise(tidy: pd.DataFrame) -> pd.DataFrame:
    def max_grade(g):
        vals = [x for x in g if x in GRADE_ORDER]
        return max(vals, key=GRADE_ORDER.index) if vals else ""

    tidy = tidy.copy()
    tidy["grade_final"] = tidy["grade"].where(tidy["grade"].isin(GRADE_ORDER), tidy["grade_from_wind"])
    return tidy.groupby("storm_id").agg(
        year=("sheet_year", "first"), name=("name", "first"), basin=("basin", "first"),
        start=("time", "min"), end=("time", "max"), n_fixes=("time", "size"),
        max_wind=("wind", "max"), min_pressure=("pressure", "min"),
        lat_min=("lat", "min"), lat_max=("lat", "max"), lon_min=("lon", "min"), lon_max=("lon", "max"),
        max_grade=("grade_final", max_grade), provisional=("provisional", "first"),
        over_land_fixes=("over_land", "sum"), parent_id=("parent_id", "first"),
    ).reset_index()


def load_aoi(repo: Path) -> dict:
    spec = repo / "ml" / "configs" / "mosdac_request_spec.yaml"
    try:
        import yaml
        return yaml.safe_load(spec.read_text(encoding="utf-8"))["area_of_interest"]
    except Exception as e:
        print(f"(using default AOI; could not read {spec}: {e})")
        return DEFAULT_AOI


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=repo / "ml" / "data")
    ap.add_argument("--imagery-start", default="2013-07-01",
                    help="earliest storm start to order imagery for (TO_VERIFY in MOSDAC archive)")
    ap.add_argument("--pre-hours", type=int, default=24)
    ap.add_argument("--post-hours", type=int, default=12)
    ap.add_argument("--max-gap-hours", type=float, default=48,
                    help="split a storm where consecutive fixes are further apart than this")
    ap.add_argument("--min-fixes", type=int, default=4,
                    help="do not order imagery for systems with fewer fixes than this (likely fragments)")
    ap.add_argument("--include-land", action="store_true",
                    help="also order imagery for systems whose basin of origin is LAND")
    args = ap.parse_args()

    src = args.root / "raw" / "imd_best_track"
    files = list(src.glob("*.xlsx"))
    if len(files) != 1:
        raise SystemExit(f"Expected exactly one .xlsx in {src}, found {len(files)}. Run Step 1/2 first.")
    print(f"reading {files[0].name} (all sheets; this can take a minute) ...")
    sheets = pd.read_excel(files[0], sheet_name=None, header=None, dtype=object)

    parts, reports, dropped_parts = [], [], []
    for name in sorted(sheets, key=lambda s: (not str(s).isdigit(), str(s))):
        df, rep, dropped = parse_sheet(sheets[name], str(name))
        reports.append(rep)
        if dropped is not None and len(dropped):
            dropped_parts.append(dropped)
        if df is not None:
            parts.append(df)
    if not parts:
        raise SystemExit("No sheet could be parsed. Send the report to Claude.")

    tidy, split_log = split_on_gaps(pd.concat(parts, ignore_index=True), args.max_gap_hours)
    storms = summarise(tidy)
    report = pd.DataFrame(reports)
    storms["land_origin"] = storms["basin"].eq("LAND")

    interim = args.root / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(interim / "imd_best_track_tidy.csv", index=False)
    storms.to_csv(interim / "storms.csv", index=False)
    report.to_csv(interim / "parse_report.csv", index=False)
    split_log.to_csv(interim / "split_log.csv", index=False)
    if dropped_parts:
        pd.concat(dropped_parts).to_csv(interim / "dropped_rows.csv", index=False)

    aoi = load_aoi(repo)
    sel = storms[storms["start"] >= pd.Timestamp(args.imagery_start)].copy()
    n_land = int(sel["land_origin"].sum())
    if not args.include_land:
        sel = sel[~sel["land_origin"]].copy()
    n_short = int((sel["n_fixes"] < args.min_fixes).sum())
    sel = sel[sel["n_fixes"] >= args.min_fixes].copy()
    sel["window_start"] = sel["start"] - pd.Timedelta(hours=args.pre_hours)
    sel["window_end"] = sel["end"] + pd.Timedelta(hours=args.post_hours)
    for k, v in aoi.items():
        sel["aoi_" + k] = v
    sel[["storm_id", "name", "basin", "max_grade", "window_start", "window_end"]
        + [c for c in sel.columns if c.startswith("aoi_")]].to_csv(
        interim / "mosdac_order_windows.csv", index=False)

    pd.set_option("display.width", 220, "display.max_colwidth", 50)
    shown = report[(report["warnings"] != "") | (report["bad_time"] > 0) | (report["out_of_range"] > 0)
                   | (report["dates_swapped"] > 0) | (report["years_fixed"] > 0)]
    print("\n=== sheets needing attention (warnings / fixed day rollovers / bad times) ===")
    print(shown[["sheet", "raw_rows", "kept", "storms", "blank_rows", "note_rows", "bad_time", "dupes",
                 "day_rollover_fixed", "dates_swapped", "years_fixed", "warnings"]].to_string(index=False) if len(shown) else "(none)")
    print("\ncolumn totals:", report[["raw_rows", "kept", "blank_rows", "note_rows", "bad_time", "dupes",
                                       "day_rollover_fixed", "dates_swapped", "years_fixed"]].sum().to_dict())
    print("\n2013 sheet detail:", report.loc[report["sheet"] == "2013",
          ["raw_rows", "kept", "blank_rows", "note_rows"]].to_dict("records"))
    big = report[report["note_rows"] > 50]["sheet"].tolist()
    if big and dropped_parts:
        dr = pd.concat(dropped_parts)
        for sh in big:
            print(f"\nsample of non-fix rows dropped from sheet {sh} (first 10; full list in dropped_rows.csv):")
            print(dr[dr["sheet"] == sh].head(10).to_string(index=False))
    print(f"\ntotal fixes: {len(tidy)}   storms: {len(storms)}   years {tidy['sheet_year'].min()}-{tidy['sheet_year'].max()}")
    print("grade labels:", tidy["grade"].value_counts(dropna=False).to_dict())
    print("over-land fixes:", int(tidy["over_land"].sum()), "  basins:", storms["basin"].value_counts(dropna=False).to_dict())

    print(f"\n=== storms split because of a gap > {args.max_gap_hours:.0f} h: {len(split_log)} split points ===")
    if len(split_log):
        print(split_log.head(25).to_string(index=False))
    dur = ((storms["end"] - storms["start"]).dt.total_seconds() / 86400).round(1)
    storms["duration_days"] = dur
    print("\nlongest storms after splitting (days):")
    print(storms.nlargest(8, "duration_days")[["storm_id", "name", "basin", "start", "end", "n_fixes", "duration_days"]]
          .to_string(index=False))
    short = storms[storms["n_fixes"] < 4]
    print(f"\nstorms with fewer than 4 fixes: {len(short)}")

    print(f"\nstorms to order imagery for (start >= {args.imagery_start}): {len(sel)}"
          f"   [{n_land} land-origin systems {'included' if args.include_land else 'excluded'}; "
          f"{n_short} with < {args.min_fixes} fixes excluded]")
    if len(sel):
        hours = (sel["window_end"] - sel["window_start"]).dt.total_seconds().sum() / 3600
        print(f"total window length: {hours:.0f} h  ->  about {hours*2:.0f} half-hourly scans per band")
        print("\nstorms per year (ordered set):")
        print(sel.groupby(sel["start"].dt.year).size().to_string())
    print(f"\nwrote files in {interim} (also split_log.csv and dropped_rows.csv)")


if __name__ == "__main__":
    main()
