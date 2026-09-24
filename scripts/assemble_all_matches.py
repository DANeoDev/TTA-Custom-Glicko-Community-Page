#!/usr/bin/env python3
"""Assembles data/raw/all_matches.csv from the immutable t0 baseline + all confirmed season CSVs.

The assembled all_matches.csv is the *derived* source of truth.
It is NEVER written to directly by the scraper. Instead:
  1. The scraper writes to data/staging/<CODE>_s<NN>_draft.csv
  2. After validation and admin approval the draft is moved to
     data/tournaments/<Folder>/matches/<CODE>_s<NN>.csv
  3. This script is then run to rebuild all_matches.csv.
"""
import csv
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
T0_CSV = RAW_DIR / "all_matches_t0.csv"
OUTPUT_CSV = RAW_DIR / "all_matches.csv"
BACKUP_DIR = RAW_DIR / "backups"
TOURNAMENTS_DIR = PROJECT_ROOT / "data" / "tournaments"

CSV_HEADERS = [
    "Tournament", "Date",
    "Player1", "Score1",
    "Player2", "Score2",
    "Player3", "Score3",
    "Player4", "Score4",
    "Player_Count",
]

TOURNAMENT_BLOCKS = [
    ("RL",                       ("RL_", "Royal League")),
    ("International_Championship",("International ", "International_")),
    ("Intermezzo_Championship",   ("Intermezzo ",)),
    ("mercurial_ladder",          ("ML_", "Mercurial")),
    ("Sodium_Ladder",             ("Sodium", "SL_")),
    ("Transcontinental_Ladder",   ("TCL ", "TCL_")),
    ("Survivors_Cup",             ("Survivors Cup", "Survivors_Cup")),
    ("French_Open",               ("French Open", "French_Open")),
    ("DC",                        ("DC_",)),
    ("NL",                        ("NL_",)),
    ("PL",                        ("PL_",)),
    ("Eiffel_Tower",              ("Eiffel Tower",)),
    ("Worlds",                    ("Worlds ", "World Championship")),
    ("Slow_Burn",                 ("Slow Burn",)),
    ("Wimbledon",                 ("Wimbledon",)),
]


def _block_key(tournament):
    for key, prefixes in TOURNAMENT_BLOCKS:
        for pfix in prefixes:
            if tournament.startswith(pfix):
                return key
    return "OTHER"


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _normalise_row(row):
    return {h: row.get(h, "") for h in CSV_HEADERS}


def _dedup_key(row):
    parts = []
    for i in range(1, 5):
        p = row.get(f"Player{i}", "").strip().lower()
        s = row.get(f"Score{i}", "")
        if p:
            try:
                parts.append((p, round(float(s), 2)))
            except (ValueError, TypeError):
                pass
    return (
        row.get("Tournament", "").strip().lower(),
        row.get("Date", "").strip(),
        tuple(sorted(parts)),
    )


def assemble(dry_run=False):
    if not T0_CSV.exists():
        raise FileNotFoundError(
            f"Baseline file not found: {T0_CSV}\n"
            "Create all_matches_t0.csv from the current all_matches.csv first."
        )

    t0_rows = _read_csv(T0_CSV)
    print(f"[t0] {len(t0_rows):,} rows from {T0_CSV.name}")

    season_rows = []
    season_files = []
    for matches_dir in sorted(TOURNAMENTS_DIR.glob("*/matches")):
        for csv_file in sorted(matches_dir.glob("*.csv")):
            rows = _read_csv(csv_file)
            if rows:
                season_rows.extend(rows)
                season_files.append(csv_file)
                print(f"  [+] {csv_file.relative_to(TOURNAMENTS_DIR)}: {len(rows):,} rows")

    print(f"[scraped] {len(season_rows):,} rows across {len(season_files)} season files")

    t0_keys = {_dedup_key(r) for r in t0_rows}
    new_only = [r for r in season_rows if _dedup_key(r) not in t0_keys]
    duplicates_dropped = len(season_rows) - len(new_only)
    print(f"[dedup] Dropped {duplicates_dropped} already in t0; {len(new_only)} new rows remain")

    all_rows = [_normalise_row(r) for r in (t0_rows + new_only)]

    blocks = defaultdict(list)
    for row in all_rows:
        blocks[_block_key(row.get("Tournament", ""))].append(row)

    for bk in blocks:
        blocks[bk].sort(key=lambda r: r.get("Date", "") or "")

    def _block_min_date(bk):
        dates = [r.get("Date", "") for r in blocks[bk] if r.get("Date")]
        return min(dates) if dates else "9999"

    ordered_blocks = sorted(blocks.keys(), key=_block_min_date)
    assembled = []
    for bk in ordered_blocks:
        assembled.extend(blocks[bk])

    print(f"[assemble] Total {len(assembled):,} rows across {len(ordered_blocks)} blocks")

    if dry_run:
        print("[dry-run] No files written.")
        return {"t0_rows": len(t0_rows), "new_rows": len(new_only), "total": len(assembled)}

    if OUTPUT_CSV.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = BACKUP_DIR / f"all_matches_{ts}.csv"
        shutil.copy2(OUTPUT_CSV, backup)
        print(f"[backup] {backup.name}")

    _write_csv(OUTPUT_CSV, assembled)
    print(f"[done] Written {len(assembled):,} rows to {OUTPUT_CSV}")

    return {
        "t0_rows": len(t0_rows),
        "new_rows": len(new_only),
        "duplicates_dropped": duplicates_dropped,
        "total": len(assembled),
        "blocks": len(ordered_blocks),
        "season_files": len(season_files),
    }


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    stats = assemble(dry_run=dry)
    print("\nSummary:", stats)
