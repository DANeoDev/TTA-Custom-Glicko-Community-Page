"""Migration script to clean duplicate matches and import genuine Intermezzo Season 7.

1. Replaces 470 fake duplicate matches of Intermezzo S7 with 800 real matches from
   data/tournaments/Intermezzo_Championship/Intermezzo Season 7.xlsx.
2. Removes 2 exact intra-tournament duplicate match rows in RL_tb_05.
3. Removes 600 duplicate matches of PL_s01 (subsumed by Premier League 1's 900 matches).
4. Rebuilds SQLite matches and pairwise_matches tables via loader.py.
5. Refreshes tournament_records and player_achievements via parse_tournaments.py.
"""
import os
import sys
import csv
import shutil
import sqlite3
from datetime import datetime, date
from pathlib import Path
import openpyxl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
BACKUP_DIR = RAW_DIR / "backups"
ALL_MATCHES_CSV = RAW_DIR / "all_matches.csv"
DB_PATH = DATA_DIR / "tta_ratings.db"
S7_XLSX_PATH = DATA_DIR / "tournaments" / "Intermezzo_Championship" / "Intermezzo Season 7.xlsx"


def get_canonical_map(conn):
    canonical = {}
    try:
        cur = conn.execute("SELECT name FROM players")
        for row in cur:
            pname = row[0]
            canonical[pname.lower()] = pname
    except Exception as e:
        print(f"Warning: could not load players canonical map: {e}")
    return canonical


def parse_genuine_s7_matches(canonical_map):
    wb = openpyxl.load_workbook(S7_XLSX_PATH, data_only=True)
    ws = wb["Results"]
    
    current_div = None
    div_game_counter = {}
    parsed_matches = []
    
    for row in ws.iter_rows(values_only=True):
        if not any(row):
            continue
        # Division header row
        if row[0] and not row[1] and not row[2]:
            current_div = str(row[0]).strip()
            div_game_counter[current_div] = 0
            continue
        
        if row[0] == "Intermezzo S7":
            div_game_counter[current_div] = div_game_counter.get(current_div, 0) + 1
            game_idx = div_game_counter[current_div]
            
            # Date
            raw_date = row[1]
            if isinstance(raw_date, (datetime, date)):
                d_str = raw_date.strftime("%Y-%m-%d")
            else:
                d_str = str(raw_date).split(" ")[0].strip()
            
            p1, s1 = str(row[2]).strip(), float(row[3])
            p2, s2 = str(row[4]).strip(), float(row[5])
            p3, s3 = str(row[6]).strip(), float(row[7])
            
            # Canonicalize names
            p1_norm = canonical_map.get(p1.lower(), p1)
            p2_norm = canonical_map.get(p2.lower(), p2)
            p3_norm = canonical_map.get(p3.lower(), p3)
            
            # Sort descending by score
            participants = [(p1_norm, s1), (p2_norm, s2), (p3_norm, s3)]
            participants.sort(key=lambda x: x[1], reverse=True)
            
            def fmt_score(val):
                return str(int(val)) if val.is_integer() else str(val)
            
            match_dict = {
                "Tournament": f"Intermezzo S7 - {current_div} game {game_idx}",
                "Date": d_str,
                "Player1": participants[0][0],
                "Score1": fmt_score(participants[0][1]),
                "Player2": participants[1][0],
                "Score2": fmt_score(participants[1][1]),
                "Player3": participants[2][0],
                "Score3": fmt_score(participants[2][1]),
                "Player4": "",
                "Score4": "",
                "Player_Count": "3"
            }
            parsed_matches.append(match_dict)
            
    return parsed_matches


def run_migration(dry_run=False):
    print("=" * 60)
    print("TTA Dataset Migration: Intermezzo S7 & Match Deduplication")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    canonical_map = get_canonical_map(conn)
    conn.close()
    
    # 1. Parse genuine S7
    print(f"\n[1/5] Parsing genuine Intermezzo Season 7 from {S7_XLSX_PATH.name}...")
    s7_matches = parse_genuine_s7_matches(canonical_map)
    print(f"Parsed {len(s7_matches)} genuine S7 matches across {len(set(m['Tournament'].split(' game ')[0] for m in s7_matches))} divisions.")
    
    # 2. Read existing all_matches.csv
    print(f"\n[2/5] Reading existing {ALL_MATCHES_CSV.name}...")
    with open(ALL_MATCHES_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        original_rows = list(reader)
    print(f"Total existing rows: {len(original_rows):,}")
    
    # 3. Filter rows
    print("\n[3/5] Filtering duplicates & fake matches...")
    new_rows = []
    dropped_s7_fake = 0
    dropped_pl_s01 = 0
    dropped_exact_dupes = 0
    
    seen_rl_dupe1 = False
    seen_rl_dupe2 = False
    
    s6_rows = []
    
    for r in original_rows:
        t = r.get("Tournament", "")
        
        # Check fake S7
        if t.startswith("Intermezzo S7"):
            dropped_s7_fake += 1
            continue
        
        # Check duplicate PL_s01
        if t == "PL_s01":
            dropped_pl_s01 += 1
            continue
        
        # Check RL_tb_05 exact duplicates
        if t == "RL_tb_05 - Best Duke game 1" and r.get("Player1") == "yaop" and r.get("Score1") == "169":
            if seen_rl_dupe1:
                dropped_exact_dupes += 1
                continue
            seen_rl_dupe1 = True
            
        if t == "RL_tb_05 - Marquess 1 places 5-6 game 1" and r.get("Player1") == "holy834" and r.get("Score1") == "132":
            if seen_rl_dupe2:
                dropped_exact_dupes += 1
                continue
            seen_rl_dupe2 = True
            
        if t.startswith("Intermezzo S6"):
            s6_rows.append(r)
            new_rows.append(r)
        else:
            # If we just finished S6 block and encounter next tournament, insert S7 matches here!
            if s6_rows and not any(m in new_rows[-1]["Tournament"] for m in ["Intermezzo S6", "Intermezzo S7"]):
                # S7 already inserted or needs insertion
                pass
            new_rows.append(r)
            
    # Find insertion index right after the last S6 row
    last_s6_idx = -1
    for idx, r in enumerate(new_rows):
        if r.get("Tournament", "").startswith("Intermezzo S6"):
            last_s6_idx = idx
            
    if last_s6_idx != -1:
        insert_pos = last_s6_idx + 1
        new_rows[insert_pos:insert_pos] = s7_matches
        print(f"Inserted {len(s7_matches)} genuine S7 matches right after Intermezzo S6 at index {insert_pos}.")
    else:
        new_rows.extend(s7_matches)
        print(f"Appended {len(s7_matches)} genuine S7 matches at the end.")
        
    print(f"Dropped {dropped_s7_fake} fake duplicate Intermezzo S7 matches.")
    print(f"Dropped {dropped_pl_s01} duplicate PL_s01 matches.")
    print(f"Dropped {dropped_exact_dupes} intra-tournament exact duplicate matches in RL_tb_05.")
    print(f"Added {len(s7_matches)} genuine Intermezzo Season 7 matches.")
    print(f"New dataset total rows: {len(new_rows):,} (Net change: {len(new_rows) - len(original_rows):+,} matches)")
    
    if dry_run:
        print("\n[DRY RUN] Completed without writing changes.")
        return
        
    # 4. Safety Backup and Write
    print("\n[4/5] Creating backups and writing updated all_matches.csv...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = BACKUP_DIR / f"all_matches_pre_s7_migration_{ts}.csv"
    shutil.copy2(ALL_MATCHES_CSV, backup_csv)
    print(f"Safety backup created at: {backup_csv.name}")
    
    with open(ALL_MATCHES_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(new_rows)
    print(f"Successfully saved updated {ALL_MATCHES_CSV.name}.")
    
    # 5. Reload into SQLite database
    print("\n[5/5] Ingesting updated matches and pairwise records into SQLite database...")
    from src.data.loader import load_matches_and_expand_pairwise
    res = load_matches_and_expand_pairwise()
    print(f"SQLite loaded {res['matches_count']:,} matches and {res['pairwise_count']:,} pairwise records.")
    
    print("\nRefreshing tournament records and player achievements...")
    from src.data.parse_tournaments import parse_all_tournaments
    parse_all_tournaments()
    
    print("\n" + "=" * 60)
    print("Migration finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    run_migration(dry_run=dry_run)
