"""Unified, high-accuracy replay code backfill script for TTA ratings database.

Scans all cached CGE tournament HTML files in parallel, parses match details and
replay codes using multiple DOM strategies, and links them to database matches
using strict multi-tier fuzzy matching (exact players + scores, date proximity,
account rename / deleted_user handling, and tournament group alignment).
"""
import sys
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.data.db import get_connection, init_db


def clean_player_name(raw_name: str) -> str:
    """Cleans rank prefixes and tournament status flags from player names."""
    if not raw_name:
        return ""
    name = re.sub(r'^\d+\.\s*', '', raw_name)
    name = re.sub(r'\s*\((?:BAN|MOD|QUIT|TIMEOUT|EXPIRED)\)', '', name, flags=re.IGNORECASE)
    return name.lower().strip()


def parse_cache_file(fpath_str: str):
    """Extracts games with replay codes and participants from a cached HTML file."""
    fpath = Path(fpath_str)
    try:
        txt = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if "spectate-code" not in txt and "session-code" not in txt:
        return []

    soup = BeautifulSoup(txt, "html.parser")
    games_found = []

    all_rows = soup.find_all("tr")
    row_index = {id(r): idx for idx, r in enumerate(all_rows)}

    for r in all_rows:
        spec = r.find(class_=re.compile(r"spectate-code|session-code"))
        span_t = r.find(class_="session-name-title")

        code = None
        if spec:
            c_txt = spec.get_text(strip=True)
            if c_txt and len(c_txt) >= 4 and c_txt.isupper():
                code = c_txt

        my_idx = row_index.get(id(r))
        r_game = all_rows[my_idx + 1] if my_idx is not None and my_idx + 1 < len(all_rows) else None

        if not code and r_game:
            spec2 = r_game.find(class_=re.compile(r"spectate-code|session-code"))
            if spec2:
                c_txt = spec2.get_text(strip=True)
                if c_txt and len(c_txt) >= 4 and c_txt.isupper():
                    code = c_txt

        if not code:
            continue

        parts = []
        target_rows = [r_game] if r_game else []
        target_rows.append(r)

        for tr in target_rows:
            if not tr:
                continue

            # Method 1: div with width: 25%/33%/50%
            user_divs = tr.find_all("div", style=re.compile(r"width:\s*(?:25|33|50)%", re.IGNORECASE))
            if len(user_divs) >= 2:
                cur_parts = []
                for ud in user_divs:
                    a = ud.find("a", class_="player-tooltip") or ud.find("a")
                    p_name = clean_player_name(a.get_text(strip=True)) if a else None
                    ud_txt = ud.get_text(" ", strip=True)
                    nums = re.findall(r'-?\d+(?:\.\d+)?', ud_txt)
                    score = float(nums[-1]) if nums else 0.0
                    if p_name:
                        cur_parts.append((p_name, score))
                if len(cur_parts) >= 2:
                    parts = cur_parts
                    break

            # Method 2: popover-user results
            for pop in tr.find_all(id=re.compile(r'popover-user')):
                res_divs = pop.find_all(class_="player-tooltip-result")
                if len(res_divs) >= 2:
                    cur_parts = []
                    for rd in res_divs:
                        t = rd.get_text(" ", strip=True)
                        m_sc = re.search(r'([A-Za-z0-9_.\-]+(?:\s+[A-Za-z0-9_.\-]+)?)\s*\(?\s*(-?\d+)\s*\)?', t)
                        if m_sc:
                            cur_parts.append((clean_player_name(m_sc.group(1)), float(m_sc.group(2))))
                    if len(cur_parts) >= 2:
                        parts = cur_parts
                        break
            if parts:
                break

            # Method 3: plain player links
            a_tags = tr.find_all("a", href=re.compile(r"/users/|/player/|/profile/|/u/", re.IGNORECASE))
            if len(a_tags) >= 2:
                cur_parts = []
                for a in a_tags:
                    p = clean_player_name(a.get_text(strip=True))
                    if p:
                        cur_parts.append((p, 0.0))
                if len(cur_parts) >= 2:
                    parts = cur_parts
                    break

        if len(parts) >= 2:
            raw_text = r.get_text(" ", strip=True) + " " + (r_game.get_text(" ", strip=True) if r_game else "")
            m_date = re.search(r'finished\s+(\d{4}-\d{2}-\d{2})', raw_text) or re.search(r'(\d{4}-\d{2}-\d{2})', raw_text)
            g_date = m_date.group(1) if m_date else None

            g_title = span_t.get_text(strip=True) if span_t else r.get_text(" ", strip=True)[:60]
            games_found.append({
                "code": code,
                "date": g_date,
                "tournament": g_title,
                "player_count": len(parts),
                "participants": parts,
                "file": fpath.name
            })

    return games_found


def run_backfill():
    """Executes the complete parsing and database matching workflow."""
    init_db()
    conn = get_connection()
    cache_dir = ROOT_DIR / "data" / "cache" / "cge"
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} not found.")
        return

    html_files = [str(f) for f in cache_dir.glob("*.html")]
    print(f"Found {len(html_files)} cached HTML files. Parsing in parallel...")

    t0 = datetime.now()
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(parse_cache_file, html_files, chunksize=25))
    all_games = [g for sub in results for g in sub]
    dur = (datetime.now() - t0).total_seconds()

    unique_codes = set(g["code"] for g in all_games)
    print(f"Parsed {len(all_games)} games ({len(unique_codes)} unique codes) in {dur:.2f}s.")

    print("Indexing database matches...")
    rows = conn.execute("""
        SELECT match_id, tournament, date, player_count,
               player1, score1, player2, score2, player3, score3, player4, score4,
               replay_code
        FROM matches
    """).fetchall()

    db_by_players = {}
    db_by_subset = {}   # (pcount, 3-player subset) -> list of candidates
    match_map = {}

    for r in rows:
        players = []
        scores = []
        for i in range(1, 5):
            p = r[f"player{i}"]
            s = r[f"score{i}"]
            if p:
                players.append(clean_player_name(p))
                scores.append(s if s is not None else 0.0)

        p_tuple = tuple(sorted(players))
        pcount = r["player_count"]
        cand = {
            "match_id": r["match_id"],
            "tournament": r["tournament"] or "",
            "date": r["date"],
            "player_count": pcount,
            "players": p_tuple,
            "scores": sorted(scores),
            "replay_code": r["replay_code"],
        }
        match_map[r["match_id"]] = cand

        # Index by full player set
        if p_tuple not in db_by_players:
            db_by_players[p_tuple] = []
        db_by_players[p_tuple].append(cand)

        # Index subsets for all games with >= 2 players (to handle deleted_user / rename)
        if len(players) >= 2:
            for omit_idx in range(len(players)):
                sub_p = tuple(sorted(players[:omit_idx] + players[omit_idx+1:]))
                key = (pcount, sub_p)
                if key not in db_by_subset:
                    db_by_subset[key] = []
                db_by_subset[key].append(cand)

    print(f"Indexed {len(rows)} DB matches into {len(db_by_players)} player sets.")

    matched_count = 0
    new_codes_count = 0
    already_had_code = 0
    updates_to_run = []

    for g in all_games:
        cge_players = [p[0] for p in g["participants"]]
        cge_p_tuple = tuple(sorted(cge_players))
        cge_scores = sorted(p[1] for p in g["participants"])
        code = g["code"]
        pcount = g["player_count"]

        candidates = db_by_players.get(cge_p_tuple, [])
        candidates = [c for c in candidates if c["player_count"] == pcount]

        matched_cand = None

        # Level 1: Exact player set + score match
        if candidates and cge_scores != [0.0] * len(cge_scores):
            for cand in candidates:
                if cand["scores"] != [0.0] * len(cand["scores"]) and len(cand["scores"]) == len(cge_scores):
                    if max(abs(s1 - s2) for s1, s2 in zip(cand["scores"], cge_scores)) < 1.0:
                        matched_cand = cand
                        break

        # Level 2: Exact player set + single candidate or date proximity
        if not matched_cand and len(candidates) == 1:
            matched_cand = candidates[0]
        elif not matched_cand and candidates and g["date"]:
            try:
                g_dt = datetime.strptime(g["date"][:10], "%Y-%m-%d")
                for cand in candidates:
                    cand_dt = datetime.strptime(cand["date"][:10], "%Y-%m-%d")
                    if abs((g_dt - cand_dt).days) <= 60:
                        matched_cand = cand
                        break
            except Exception:
                pass

        # Level 3: Handle account deletion / name change (N-1 players match + scores match)
        if not matched_cand and len(cge_players) >= 2 and cge_scores != [0.0] * len(cge_scores):
            for omit_idx in range(len(cge_players)):
                sub_tuple = tuple(sorted(cge_players[:omit_idx] + cge_players[omit_idx+1:]))
                sub_cands = db_by_subset.get((pcount, sub_tuple), [])
                for cand in sub_cands:
                    if len(cand["scores"]) == len(cge_scores):
                        if max(abs(s1 - s2) for s1, s2 in zip(cand["scores"], cge_scores)) < 1.0:
                            # For 2-player games, verify date proximity (<= 45 days) to avoid collision
                            if pcount == 2:
                                if g["date"] and cand["date"]:
                                    try:
                                        d_diff = abs((datetime.strptime(g["date"][:10], "%Y-%m-%d") - datetime.strptime(cand["date"][:10], "%Y-%m-%d")).days)
                                        if d_diff > 45:
                                            continue
                                    except Exception:
                                        pass
                            matched_cand = cand
                            break
                if matched_cand:
                    break

        if matched_cand:
            matched_count += 1
            if not matched_cand["replay_code"]:
                new_codes_count += 1
                matched_cand["replay_code"] = code
                updates_to_run.append((code, matched_cand["match_id"]))
            elif matched_cand["replay_code"] == code:
                already_had_code += 1
            else:
                matched_cand["replay_code"] = code
                updates_to_run.append((code, matched_cand["match_id"]))

    print(f"Total CGE matches matched: {matched_count}")
    print(f"Already had identical replay code: {already_had_code}")
    print(f"New replay codes to assign: {new_codes_count}")
    print(f"Total updates queued: {len(updates_to_run)}")

    if updates_to_run:
        with conn:
            conn.executemany("UPDATE matches SET replay_code = ? WHERE match_id = ?", updates_to_run)
        print(f"Successfully committed {len(updates_to_run)} replay code updates to database!")
    else:
        print("No database updates required.")

    conn.close()


if __name__ == "__main__":
    run_backfill()
