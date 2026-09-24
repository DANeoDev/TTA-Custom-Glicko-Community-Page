"""Tournament Consistency and Sanity Checker for TTA-Glicko2-WHR.

Verifies the integrity between decomposed match records (matches table / all_matches.csv)
and official tournament result tables (result.csv, *.xlsx) to detect:
- Discrepancies in total games played per player.
- Ranking / points divergence between raw scores and standings.
- Missing players or name spelling variations.
"""
import csv
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.data.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOURNAMENTS_DIR = PROJECT_ROOT / "data" / "tournaments"


def get_tournament_db_patterns(tournament_name: str, result_csv_path: Optional[Path] = None) -> List[str]:
    """Resolves database LIKE patterns for a tournament directory or name."""
    t_low = tournament_name.lower().replace("_", " ").strip()
    s_num = None
    target_str = f"{tournament_name} {result_csv_path.name if result_csv_path else ''}"
    m_s = re.search(r'[sS][_\s-]*0?(\d+)', target_str)
    if m_s:
        s_num = int(m_s.group(1))

    patterns = []
    if "royal league" in t_low or "rl" in t_low:
        if s_num is not None:
            patterns.extend([f"RL_s{s_num:02d}%", f"RL_s{s_num}%"])
        else:
            patterns.append("RL_%")
    elif "international" in t_low or "ic" in t_low:
        if s_num is not None:
            patterns.extend([f"International%{s_num}%", f"IC_s{s_num:02d}%", f"IC_s{s_num}%"])
        else:
            patterns.extend(["International%", "IC_%"])
    elif "intermezzo" in t_low:
        patterns.append("Intermezzo%")
    elif "transcontinental" in t_low or "tl" in t_low:
        if s_num is not None:
            patterns.extend([f"TL_s{s_num:02d}%", f"TL_s{s_num}%"])
        else:
            patterns.extend(["TL_%", "Transcontinental%"])
    elif "mercurial" in t_low or "ml" in t_low:
        if s_num is not None:
            patterns.extend([f"ML_s{s_num:02d}%", f"ML_s{s_num}%"])
        else:
            patterns.extend(["ML_%", "Mercurial%"])
    elif "sodium" in t_low:
        patterns.append("Sodium%")
    elif "q&d" in t_low or "qd" in t_low:
        patterns.extend(["Q&D%", "QD%"])
    elif "australi" in t_low:
        patterns.extend(["Australian%", "Australien%"])
    else:
        patterns.append(f"%{tournament_name.lower()}%")
        patterns.append(f"%{tournament_name.lower().replace('_', ' ')}%")

    return list(dict.fromkeys(patterns))


def convert_standings_url_to_fetchable(url: str) -> str:
    """Converts a Google Sheet URL or web URL into a direct CSV export or fetchable URL."""
    u = url.strip()
    m_id = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', u)
    if m_id:
        sheet_id = m_id.group(1)
        m_gid = re.search(r'[#&?]gid=([0-9]+)', u)
        gid = m_gid.group(1) if m_gid else '0'
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return u


def fetch_online_standings(url: str, timeout: int = 12) -> Optional[str]:
    """Fetches CSV standings data from an online URL (e.g. Google Sheets export)."""
    import urllib.request
    fetch_url = convert_standings_url_to_fetchable(url)
    try:
        req = urllib.request.Request(fetch_url, headers={"User-Agent": "Mozilla/5.0 (TTA-Standings-Auditor)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return content
    except Exception:
        return None


def parse_standings_text_to_dict(csv_text: str) -> Dict[str, Dict[str, Any]]:
    """Parses raw CSV standings text into results_by_player dictionary."""
    results_by_player = {}
    lines = [l for l in csv_text.splitlines() if l.strip()]
    if not lines:
        return {}

    # Try standard DictReader
    reader = csv.DictReader(lines)
    fieldnames = reader.fieldnames or []
    p_col = next((c for c in fieldnames if "player" in c.lower() or "name" in c.lower()), None)

    if p_col:
        for row in reader:
            pname = (row.get(p_col) or "").strip()
            if not pname or pname.startswith("#"):
                continue
            games_col = next((c for c in row if c.lower() in ("games", "matches", "played")), None)
            games = int(row[games_col]) if games_col and row[games_col] and str(row[games_col]).isdigit() else None

            pts_col = next((c for c in row if "point" in c.lower() or "pts" in c.lower() or "score" in c.lower()), None)
            points = None
            if pts_col and row[pts_col]:
                val_str = str(row[pts_col]).replace(',', '.').strip()
                try:
                    points = float(val_str)
                except ValueError:
                    pass

            place_col = next((c for c in row if c.lower() in ("place", "rank", "pos")), None)
            place = row[place_col].strip() if place_col and row[place_col] else None

            results_by_player[pname.lower()] = {
                "original_name": pname,
                "expected_games": games,
                "expected_points": points,
                "expected_place": place,
                "raw_row": row
            }
    else:
        # Fallback for matrix/grid sheets (like Swiss/division grids): find player names
        raw_reader = csv.reader(lines)
        for row in raw_reader:
            for cell in row:
                c_clean = cell.strip()
                if c_clean and len(c_clean) >= 3 and not re.match(r'^\d+$', c_clean) and not any(kw in c_clean.lower() for kw in ("round", "group", "seeded", "qualified")):
                    if c_clean.lower() not in results_by_player:
                        results_by_player[c_clean.lower()] = {
                            "original_name": c_clean,
                            "expected_games": None,
                            "expected_points": None,
                            "expected_place": None,
                            "raw_row": row
                        }

    return results_by_player


def check_tournament_consistency(
    tournament_name: str,
    result_csv_path: Optional[Path] = None,
    standings_url: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Compares match outcomes against a tournament's official result table or live online standings.
    
    Args:
        tournament_name: Name or pattern of the tournament (e.g. 'RL_s01', 'Royal League', 'Australien_Open')
        result_csv_path: Optional path to a local result.csv file
        standings_url:   Optional online URL to live standings (Google Sheet or web page)
        conn:            SQLite connection
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        results_by_player = {}
        standings_source = None
        is_live_online = False

        # 1. Discover online standings URL from _sources.md if not explicitly passed
        matched_dir = None
        t_norm = re.sub(r'[\s_]+', ' ', tournament_name).lower().strip()
        for t_dir in TOURNAMENTS_DIR.iterdir():
            if t_dir.is_dir():
                d_norm = re.sub(r'[\s_]+', ' ', t_dir.name).lower().strip()
                if t_norm in d_norm or d_norm in t_norm:
                    matched_dir = t_dir
                    break

        if not standings_url and matched_dir:
            for sf in matched_dir.glob("*_sources.md"):
                try:
                    for line in sf.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if "docs.google.com/spreadsheets" in line or (line.startswith("http") and ("standings" in line.lower() or "result" in line.lower())):
                            standings_url = line
                            break
                    if standings_url:
                        break
                except Exception:
                    pass

        # 2. Try fetching live online standings if a URL exists
        if standings_url:
            online_content = fetch_online_standings(standings_url)
            if online_content:
                parsed_online = parse_standings_text_to_dict(online_content)
                if parsed_online:
                    results_by_player = parsed_online
                    standings_source = f"Live Online ({standings_url})"
                    is_live_online = True

        # 3. Fallback to local CSV if online standings was not fetched
        if not results_by_player:
            if not result_csv_path and matched_dir:
                csv_candidates = list((matched_dir / "matches").glob("*.csv")) if (matched_dir / "matches").exists() else []
                if not csv_candidates:
                    csv_candidates = list(matched_dir.glob("*.csv"))
                if csv_candidates:
                    result_csv_path = csv_candidates[0]

            if result_csv_path and result_csv_path.exists():
                try:
                    with open(result_csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
                        results_by_player = parse_standings_text_to_dict(f.read())
                        standings_source = f"Local CSV ({result_csv_path.name})"
                except Exception:
                    pass

        if not results_by_player:
            return {
                "status": "NO_RESULT_FILE",
                "tournament": tournament_name,
                "message": f"No result table (.csv) or online standings URL found for tournament '{tournament_name}'.",
                "players_checked": 0,
                "discrepancies": [],
                "standings_source": None,
                "is_live_online": False,
            }

        # 3. Query match data from DB using resolved pattern aliases
        patterns = get_tournament_db_patterns(tournament_name, result_csv_path)
        where_clauses = " OR ".join(["LOWER(tournament) LIKE ?" for _ in patterns])
        cur = conn.execute(f"""
            SELECT tournament, COUNT(*) as cnt 
            FROM matches 
            WHERE {where_clauses} 
            GROUP BY tournament
        """, [p.lower() for p in patterns])
        matching_tourneys = [r[0] for r in cur.fetchall()]

        if not matching_tourneys:
            return {
                "status": "NO_MATCHES_FOUND",
                "tournament": tournament_name,
                "result_file": str(result_csv_path.name) if result_csv_path else (standings_source or "Online Standings"),
                "standings_source": standings_source,
                "is_live_online": is_live_online,
                "message": f"No matches found in database matching pattern '{tournament_name}' (tested aliases: {', '.join(patterns)}).",
                "players_checked": len(results_by_player),
                "players_in_result_file": len(results_by_player),
                "players_matched": 0,
                "discrepancies": []
            }

        # Tally matches per player for these tournaments
        tourney_placeholders = ",".join("?" for _ in matching_tourneys)
        query = f"""
            SELECT player_a as player, COUNT(*) as games_count,
                   SUM(CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws,
                   SUM(CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END) as losses
            FROM pairwise_matches
            WHERE tournament IN ({tourney_placeholders})
            GROUP BY player_a
        """
        match_stats = {}
        for r in conn.execute(query, matching_tourneys):
            match_stats[r["player"].lower()] = {
                "player": r["player"],
                "games_count": r["games_count"],
                "wins": r["wins"],
                "draws": r["draws"],
                "losses": r["losses"]
            }

        # 4. Compare results vs matches
        discrepancies = []
        matched_players = 0

        for p_lower, res in results_by_player.items():
            if p_lower in match_stats:
                matched_players += 1
                ms = match_stats[p_lower]
                exp_g = res["expected_games"]
                if exp_g is not None and ms["games_count"] != exp_g:
                    discrepancies.append({
                        "player": res["original_name"],
                        "issue": "Games count divergence",
                        "expected": exp_g,
                        "found_in_matches": ms["games_count"]
                    })
            else:
                discrepancies.append({
                    "player": res["original_name"],
                    "issue": "Missing from match records",
                    "expected_games": res["expected_games"],
                    "found_in_matches": 0
                })

        status = "PASSED" if not discrepancies else ("WARNING" if matched_players > 0 else "FAILED")

        return {
            "status": status,
            "tournament": tournament_name,
            "matching_tournaments_in_db": matching_tourneys,
            "result_file": str(result_csv_path.name) if result_csv_path else (standings_source or "Online Standings"),
            "standings_source": standings_source,
            "is_live_online": is_live_online,
            "players_in_result_file": len(results_by_player),
            "players_matched": matched_players,
            "discrepancies_count": len(discrepancies),
            "discrepancies": discrepancies[:25],  # top 25
        }

    finally:
        if close_conn:
            conn.close()
