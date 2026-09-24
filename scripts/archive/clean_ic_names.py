import re
import sys
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import get_connection
from src.data.merger import export_update_snapshot

def clean_ic_s34_string(s: str) -> str:
    m = re.search(r'^International S(\d+)\s*-\s*(?:International\s+Championship|Inter\S*(?:\s+Championship)?)\s+(.+?)\s+game\s+(\d+)$', str(s), re.IGNORECASE)
    if m:
        s_num = m.group(1)
        div = m.group(2).strip()
        g_num = m.group(3).strip()
        return f"International S{s_num} - {div} game {g_num}"
    return str(s)

def main():
    # 1. Clean IC_s34.csv
    ic_path = Path("data/tournaments/International_Championship/matches/IC_s34.csv")
    if ic_path.exists():
        df_ic = pd.read_csv(ic_path)
        df_ic["Tournament"] = df_ic["Tournament"].apply(clean_ic_s34_string)
        df_ic.to_csv(ic_path, index=False)
        print(f"Cleaned {ic_path.name}: {len(df_ic)} rows")

    # 2. Clean all_matches.csv
    all_path = Path("data/raw/all_matches.csv")
    if all_path.exists():
        df_all = pd.read_csv(all_path)
        before_bad = df_all["Tournament"].str.contains(r"Inter\.\.\.", na=False).sum()
        df_all["Tournament"] = df_all["Tournament"].apply(clean_ic_s34_string)
        after_bad = df_all["Tournament"].str.contains(r"Inter\.\.\.", na=False).sum()
        df_all.to_csv(all_path, index=False)
        print(f"Cleaned all_matches.csv: {len(df_all)} total rows (ellipsis rows reduced from {before_bad} to {after_bad})")

    # 3. Clean SQLite matches & pairwise_matches
    conn = get_connection()
    cur = conn.execute("SELECT match_id, tournament FROM matches WHERE tournament LIKE 'International S34%'")
    rows = cur.fetchall()
    cleaned_count = 0
    with conn:
        for r in rows:
            orig = r["tournament"]
            cleaned = clean_ic_s34_string(orig)
            if cleaned != orig:
                conn.execute("UPDATE matches SET tournament = ? WHERE match_id = ?", (cleaned, r["match_id"]))
                conn.execute("UPDATE pairwise_matches SET tournament = ? WHERE match_id = ?", (cleaned, r["match_id"]))
                cleaned_count += 1

    conn.close()
    print(f"Updated {cleaned_count} matches in SQLite database.")

    # 4. Re-export update snapshot
    snap = export_update_snapshot()
    print(f"Snapshot refreshed: {snap['tournaments_file']} with {snap['tournaments_count']} tournaments.")

if __name__ == "__main__":
    main()
