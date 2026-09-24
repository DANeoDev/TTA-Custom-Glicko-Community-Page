"""Backfill replay codes into the matches database table from cached CGE HTML files."""
import sys
from pathlib import Path
from datetime import datetime
import re
from concurrent.futures import ProcessPoolExecutor

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.data.db import get_connection, init_db
from src.scrapers.cge import CGEClient

def parse_file(fpath_str):
    try:
        f = Path(fpath_str)
        html = f.read_text(encoding="utf-8", errors="ignore")
        if "spectate-code" not in html and "session-code" not in html:
            return []
        parsed = CGEClient.parse_tournament_html(html, target=f.stem)
        games_out = []
        for g in parsed.get("games", []):
            code = g.get("replay_code")
            if not code:
                continue
            parts = g.get("participants", [])
            if len(parts) < 2:
                continue
            games_out.append({
                "code": code,
                "date": g.get("date"),
                "tournament": g.get("tournament", ""),
                "raw_row": g.get("raw_row", ""),
                "player_count": len(parts),
                "participants": parts,
            })
        return games_out
    except Exception:
        return []

def run_backfill():
    init_db()
    conn = get_connection()
    cache_dir = ROOT_DIR / "data" / "cache" / "cge"
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} not found.")
        return

    html_files = [str(f) for f in cache_dir.glob("*.html")]
    print(f"Found {len(html_files)} cached HTML files. Parsing in parallel...")

    start_t = datetime.now()
    all_cge_games = []
    with ProcessPoolExecutor() as executor:
        for res in executor.map(parse_file, html_files, chunksize=20):
            all_cge_games.extend(res)

    dur = (datetime.now() - start_t).total_seconds()
    print(f"Parsed {len(all_cge_games)} CGE games with replay codes in {dur:.2f}s.")

    print("Indexing existing matches from database...")
    rows = conn.execute("""
        SELECT match_id, tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4, replay_code
        FROM matches
    """).fetchall()

    db_by_players = {}
    for r in rows:
        players = []
        scores = []
        for i in range(1, 5):
            p = r[f"player{i}"]
            s = r[f"score{i}"]
            if p:
                players.append(p.lower().strip())
                scores.append(s if s is not None else 0.0)
        p_key = tuple(sorted(players))
        if p_key not in db_by_players:
            db_by_players[p_key] = []
        db_by_players[p_key].append({
            "match_id": r["match_id"],
            "tournament": r["tournament"] or "",
            "date": r["date"],
            "player_count": r["player_count"],
            "players": p_key,
            "scores": sorted(scores),
            "replay_code": r["replay_code"],
        })

    print(f"Indexed {len(rows)} database matches into {len(db_by_players)} player combinations.")

    updates_to_run = []
    matched_count = 0
    already_had_code = 0

    for g in all_cge_games:
        parts = g["participants"]
        cge_players = tuple(sorted(p[0].lower().strip() for p in parts))
        cge_scores = sorted(p[1] for p in parts)
        cge_date_str = g["date"]
        cge_pcount = g["player_count"]
        cge_raw = g["raw_row"].lower()
        cge_tourney = g["tournament"].lower()
        code = g["code"]

        candidates = db_by_players.get(cge_players, [])
        if not candidates:
            continue

        # Filter by player count
        candidates = [c for c in candidates if c["player_count"] == cge_pcount]
        if not candidates:
            continue

        # Filter by scores if scores exist in DB
        matching_scores = []
        for cand in candidates:
            if len(cand["scores"]) == len(cge_scores):
                score_diff = max(abs(s1 - s2) for s1, s2 in zip(cand["scores"], cge_scores))
                if score_diff < 0.2:
                    matching_scores.append(cand)
        if matching_scores:
            candidates = matching_scores

        # Check game number if available
        g_num_match = re.search(r'game\s+(\d+)', cge_raw) or re.search(r'game\s+(\d+)', cge_tourney)
        if g_num_match:
            g_num = g_num_match.group(1)
            same_g_num = [c for c in candidates if re.search(rf'game\s+{g_num}\b', c["tournament"].lower())]
            if same_g_num:
                candidates = same_g_num

        # Pick best candidate by date proximity
        best_cand = None
        min_days = 999999
        try:
            c_dt = datetime.strptime(cge_date_str[:10], "%Y-%m-%d")
            for cand in candidates:
                cand_dt = datetime.strptime(cand["date"][:10], "%Y-%m-%d")
                days = abs((c_dt - cand_dt).days)
                if days < min_days:
                    min_days = days
                    best_cand = cand
        except Exception:
            if candidates:
                best_cand = candidates[0]
                min_days = 0

        # Allow date difference up to 60 days
        if best_cand and min_days <= 60:
            matched_count += 1
            if not best_cand["replay_code"]:
                best_cand["replay_code"] = code
                updates_to_run.append((code, best_cand["match_id"]))
            elif best_cand["replay_code"] == code:
                already_had_code += 1
            else:
                best_cand["replay_code"] = code
                updates_to_run.append((code, best_cand["match_id"]))

    print(f"Total CGE matches matched: {matched_count}")
    print(f"Already had identical replay code: {already_had_code}")
    print(f"Prepared {len(updates_to_run)} match updates.")

    if updates_to_run:
        with conn:
            conn.executemany("UPDATE matches SET replay_code = ? WHERE match_id = ?", updates_to_run)
        print(f"Successfully updated {len(updates_to_run)} matches with replay codes!")
    else:
        print("No new matches needed updating.")

    conn.close()

if __name__ == '__main__':
    run_backfill()
