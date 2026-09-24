"""Safe append-only match data merger and historical integrity manager.

Guarantees historical immutability by:
1. Creating timestamped backups in data/raw/backups/ before any disk write.
2. Deduplicating new matches against the complete historical record.
3. Normalizing player aliases to canonical database names.
4. Safely appending new verified matches to all_matches.csv and SQLite tables.
"""
import csv
import os
import re
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set, Union

from src.data.db import get_connection

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
ALL_MATCHES_CSV = RAW_DATA_DIR / "all_matches.csv"
ALL_MATCHES_T0_CSV = RAW_DATA_DIR / "all_matches_t0.csv"
BACKUP_DIR = RAW_DATA_DIR / "backups"
TOURNAMENTS_DIR = PROJECT_ROOT / "data" / "tournaments"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
UPDATES_DIR = PROJECT_ROOT / "data" / "updates"


def make_dedup_key(tournament: str, date: str, participants: List[Tuple[str, float]]) -> Tuple[str, str, Tuple[Tuple[str, float], ...]]:
    """Builds an invariant deduplication key for a match."""
    t_clean = (tournament or "").strip().lower()
    d_clean = (date or "").strip()
    # Sort participants by lowercase name to be invariant to table seating / order variations
    sorted_parts = tuple(sorted([(p[0].strip().lower(), round(float(p[1]), 2)) for p in participants]))
    return (t_clean, d_clean, sorted_parts)


def get_ingested_seasons_from_all_matches(
    tournament_name: str,
    all_matches_path: Optional[Path] = None
) -> Set[int]:
    """Returns a set of season/stage numbers already present in all_matches.csv for this tournament."""
    csv_path = all_matches_path or ALL_MATCHES_CSV
    if not csv_path.exists():
        csv_path = ALL_MATCHES_T0_CSV
    if not csv_path.exists():
        return set()

    t_lower = tournament_name.lower().replace("_", " ")
    seasons = set()

    if 'royal' in t_lower or re.search(r'\brl\b', t_lower):
        pattern = r'RL_s0?(\d+)'
    elif 'international' in t_lower or re.search(r'\bic\b', t_lower):
        pattern = r'International\s+S0?(\d+)'
    elif 'intermezzo' in t_lower or re.search(r'\biz\b', t_lower):
        pattern = r'Intermezzo\s+S0?(\d+)'
    elif 'survivor' in t_lower:
        pattern = r'Survivors\s*Cup.*?Stage\s*0?(\d+)'
    elif 'french open' in t_lower or re.search(r'\bfo\b', t_lower):
        pattern = r'French\s*Open.*?Stage\s*0?(\d+)'
    elif 'world' in t_lower or re.search(r'\bwc\b', t_lower):
        pattern = r'(?:World\s*Championship|Worlds)\s*2026.*?stage\s*0?(\d+)'
    elif 'transcontinental' in t_lower or re.search(r'\btcl\b|\btl\b', t_lower):
        pattern = r'(?:Transcontinental|TCL).*?(?:Round|Stage)\s*0?(\d+)'
    elif 'mercurial' in t_lower or re.search(r'\bml\b', t_lower):
        pattern = r'(?:Mercurial|ML).*?Season\s*0?(\d+)'
    elif 'sodium' in t_lower or re.search(r'\bsl\b', t_lower):
        pattern = r'(?:Sodium|SL).*?Season\s*0?(\d+)'
    elif 'slow burn' in t_lower or re.search(r'\bsb\b', t_lower):
        pattern = r'Slow\s*Burn.*?(?:Season|stage|s)\s*0?(\d+)'
    else:
        pattern = r'(?:Season|Stage|Round)\s*0?(\d+)'

    try:
        with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                t_val = r.get("Tournament", "")
                m = re.search(pattern, t_val, re.IGNORECASE)
                if m:
                    seasons.add(int(m.group(1)))
    except Exception:
        pass

    return seasons


def get_ingested_seasons_for_tournament(tournament_name: str, db_path: Optional[Path] = None) -> List[int]:
    """Returns a sorted list of season numbers already present in all_matches.csv or the database for this tournament."""
    # Preferred source: all_matches.csv
    csv_seasons = get_ingested_seasons_from_all_matches(tournament_name)
    if csv_seasons:
        return sorted(list(csv_seasons))

    conn = get_connection(db_path)
    seasons = set()
    t_lower = tournament_name.lower()
    try:
        import re
        if 'royal' in t_lower or 'rl' in t_lower:
            pattern = 'RL_s%'
            regex = r'RL_s0?(\d+)'
        elif 'international' in t_lower:
            pattern = 'International S%'
            regex = r'International S(\d+)'
        elif 'intermezzo' in t_lower:
            pattern = 'Intermezzo S%'
            regex = r'Intermezzo S(\d+)'
        else:
            pattern = f'%{tournament_name}%'
            regex = r'Season\s*(\d+)'

        cur = conn.execute('SELECT DISTINCT tournament FROM matches WHERE tournament LIKE ?', (pattern,))
        for r in cur:
            m = re.search(regex, r[0], re.IGNORECASE)
            if m:
                seasons.add(int(m.group(1)))
    finally:
        conn.close()

    return sorted(list(seasons))



def get_canonical_player_map(conn: Optional[sqlite3.Connection] = None) -> Dict[str, str]:
    """Builds a lowercase -> canonical player name lookup dictionary."""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    canonical = {}
    try:
        cur = conn.execute("SELECT name FROM players")
        for row in cur:
            pname = row[0]
            canonical[pname.lower()] = pname
    except Exception:
        pass
    finally:
        if close_conn:
            conn.close()

    return canonical


def load_existing_dedup_keys(csv_path: Optional[Path] = None) -> set:
    """Reads all_matches.csv and builds the set of deduplication keys for existing matches."""
    path = csv_path or ALL_MATCHES_CSV
    if not path.exists():
        return set()

    existing_keys = set()
    with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = row.get("Tournament", "")
            d = row.get("Date", "")
            participants = []
            for i in range(1, 5):
                p_name = row.get(f"Player{i}", "").strip()
                s_val = row.get(f"Score{i}", "")
                if p_name and s_val != "":
                    try:
                        participants.append((p_name, float(s_val)))
                    except ValueError:
                        pass
            if len(participants) >= 2:
                key = make_dedup_key(t, d, participants)
                existing_keys.add(key)

    return existing_keys


def create_safety_backup(source_csv: Optional[Path] = None) -> Path:
    """Creates a timestamped safety backup of all_matches.csv."""
    src = source_csv or ALL_MATCHES_CSV
    if not src.exists():
        raise FileNotFoundError(f"Cannot backup non-existent file: {src}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"all_matches_{timestamp}.csv"
    shutil.copy2(src, backup_path)
    return backup_path


def is_valid_match_record(m: Dict[str, Any]) -> bool:
    """Validates that a candidate match record satisfies TTA domain constraints.

    Guards against scraping generic platform tables, lobby capacity strings,
    and corrupted score outputs.
    """
    t_name = (m.get("tournament") or "").strip()
    d_str = (m.get("date") or "").strip()
    parts = m.get("participants", [])

    if not t_name or not d_str:
        return False
    if d_str < "2026-01-01":
        return False

    # Block platform directory artifacts and empty lobby tables
    t_lower = t_name.lower()
    if "players :" in t_lower or "/ ∞" in t_name or "no finished games" in t_lower or "cge online" in t_lower:
        return False

    p_count = len(parts)
    if p_count not in (2, 3, 4):
        return False

    for item in parts:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            return False
        p_name, s_val = item[0], item[1]
        p_str = str(p_name).strip()
        if not p_str or "players :" in p_str.lower() or "/ ∞" in p_str or "no finished games" in p_str.lower():
            return False
        try:
            score = float(s_val)
        except (ValueError, TypeError):
            return False
        # TTA scores range from 0-550 (timeouts/resigns are -1.0; bounds [-5.0, 1000.0])
        if score < -5.0 or score > 1000.0:
            return False

    return True


def preview_scraped_matches(
    scraped_games: List[Dict[str, Any]],
    csv_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Compares candidate matches against existing dataset and returns a diff summary."""
    existing_keys = load_existing_dedup_keys(csv_path)
    canonical_map = get_canonical_player_map()

    to_add = []
    duplicates = 0

    # Filter out corrupted / invalid records upfront
    valid_scraped = [g for g in scraped_games if is_valid_match_record(g)]

    for g in valid_scraped:
        raw_parts = g.get("participants", [])
        if len(raw_parts) < 2:
            continue

        # Normalize names
        normalized_parts = []
        for p_name, score in raw_parts:
            norm_name = canonical_map.get(p_name.strip().lower(), p_name.strip())
            normalized_parts.append((norm_name, float(score)))

        # Sort descending by score for standard placement format
        normalized_parts.sort(key=lambda x: x[1], reverse=True)

        key = make_dedup_key(g.get("tournament", ""), g.get("date", ""), normalized_parts)
        if key in existing_keys:
            duplicates += 1
        else:
            to_add.append({
                "tournament": g.get("tournament", "").strip(),
                "date": g.get("date", "").strip(),
                "player_count": len(normalized_parts),
                "participants": normalized_parts,
            })
            existing_keys.add(key)  # prevent duplicates within the candidate batch itself

    return {
        "total_scraped": len(scraped_games),
        "duplicate_count": duplicates,
        "new_matches_count": len(to_add),
        "new_matches": to_add,
    }


def commit_new_matches(
    new_matches: List[Dict[str, Any]],
    csv_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    create_backup: bool = True,
    commit_to_db: bool = True,
    glicko_eligible: bool = True,
    tournaments_dir: Optional[Path] = None,
    updates_dir: Optional[Path] = None,
    export_snapshot: bool = True
) -> Dict[str, Any]:
    """Appends verified new matches to all_matches.csv and SQLite database."""
    # Enforce strict 2026+ boundary and domain sanity checks
    new_matches = [m for m in new_matches if is_valid_match_record(m)]
    if not new_matches:
        return {"status": "skipped", "message": "No valid matches after 2026-01-01 cutoff to append."}

    path = csv_path or ALL_MATCHES_CSV
    backup_file = None
    if create_backup and path.exists():
        backup_file = create_safety_backup(path)

    # 1. Append rows to all_matches.csv
    file_exists = path.exists()
    if file_exists and path.stat().st_size > 0:
        try:
            with open(path, "rb+") as bf:
                bf.seek(-1, os.SEEK_END)
                if bf.read(1) != b"\n":
                    bf.write(b"\n")
        except Exception as e:
            logger.warning(f"Could not verify trailing newline on {path}: {e}")

    rows_written = 0

    with open(path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Tournament", "Date",
                "Player1", "Score1",
                "Player2", "Score2",
                "Player3", "Score3",
                "Player4", "Score4",
                "Player_Count"
            ])

        for m in new_matches:
            parts = m["participants"]
            p_count = len(parts)

            p1, s1 = parts[0]
            p2, s2 = parts[1]
            p3 = parts[2][0] if p_count > 2 else ""
            s3 = parts[2][1] if p_count > 2 else ""
            p4 = parts[3][0] if p_count > 3 else ""
            s4 = parts[3][1] if p_count > 3 else ""

            writer.writerow([
                m["tournament"],
                m["date"],
                p1, s1,
                p2, s2,
                p3, s3,
                p4, s4,
                p_count
            ])
            rows_written += 1

    pairwise_inserted = 0
    if commit_to_db:
        # 2. Insert into SQLite matches & pairwise_matches incrementally
        conn = get_connection(db_path)
        with conn:
            # Get next match_id
            cur = conn.execute("SELECT COALESCE(MAX(match_id), 0) FROM matches")
            next_id = cur.fetchone()[0]

            for m in new_matches:
                next_id += 1
                parts = m["participants"]
                p_count = len(parts)
                p1, s1 = parts[0]
                p2, s2 = parts[1]
                p3 = parts[2][0] if p_count > 2 else None
                s3 = parts[2][1] if p_count > 2 else None
                p4 = parts[3][0] if p_count > 3 else None
                s4 = parts[3][1] if p_count > 3 else None

                # Eligibility flag per match or default
                is_eligible = int(m.get("glicko_eligible", 1 if glicko_eligible else 0))
                replay_code = m.get("replay_code")

                conn.execute("""
                    INSERT INTO matches (
                        match_id, tournament, date, player_count,
                        player1, score1, player2, score2, player3, score3, player4, score4,
                        glicko_eligible, replay_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_id, m["tournament"], m["date"], p_count,
                    p1, s1, p2, s2, p3, s3, p4, s4,
                    is_eligible, replay_code
                ))

                weight = 1.0 / float(p_count - 1)
                for i in range(p_count):
                    for j in range(i + 1, p_count):
                        pa, sa = parts[i]
                        pb, sb = parts[j]
                        if sa > sb:
                            out_a = 1.0
                        elif sa < sb:
                            out_a = 0.0
                        else:
                            out_a = 0.5

                        conn.execute("""
                            INSERT INTO pairwise_matches (
                                match_id, date, tournament, player_count,
                                player_a, player_b, score_a, score_b, outcome_a, weight,
                                glicko_eligible
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            next_id, m["date"], m["tournament"], p_count,
                            pa, pb, sa, sb, out_a, weight,
                            is_eligible
                        ))
                        pairwise_inserted += 1

        conn.close()

    # 3. Create per-tournament directory and per-season CSVs
    season_files_updated = save_season_matches_to_tournament_folder(new_matches, tournaments_dir=tournaments_dir)

    # 4. Save update snapshot to data/updates/{date}_tournaments.txt and {date}_all_games.csv
    if export_snapshot:
        try:
            export_update_snapshot(
                all_matches_path=path,
                tournaments_dir=tournaments_dir,
                updates_dir=updates_dir
            )
        except Exception as e:
            logger.warning(f"Failed to export update snapshot: {e}")

    return {
        "status": "success",
        "rows_appended": rows_written,
        "pairwise_inserted": pairwise_inserted,
        "backup_created": str(backup_file.name) if backup_file else None,
        "season_files_updated": season_files_updated,
    }


def resolve_tournament_folder_and_season(tournament_str: str) -> Tuple[str, Optional[int], str]:
    """Resolves the tournament directory name, season number, and CSV code prefix from a match tournament string.

    Returns:
        (folder_name, season_num, csv_code)
        e.g. ('Royal_League', 9, 'RL') → writes to Royal_League/matches/RL_s09.csv
    """
    # 1. Royal League
    if re.search(r'(?:\bRoyal[_\s]+League\b|\bRL\b)', tournament_str, re.IGNORECASE) or re.search(r'\bRL_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_rl = re.search(r'(?:\bRoyal[_\s]+League\b|\bRL)[_\s]*(?:Season|s)?_?0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_rl.group(1)) if m_rl and m_rl.group(1) else None
        return "Royal_League", s_num, "RL"

    # 2. International Championship (MUST have word boundary so 'Arsenic' does not match!)
    if re.search(r'(?:\bInternational(?:\s+Championship)?\b|\bIC\b)', tournament_str, re.IGNORECASE) or re.search(r'\bIC_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_ic = re.search(r'(?:\bInternational(?:\s+Championship)?\b|\bIC)[_\s]*(?:Season|s)?_?0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_ic.group(1)) if m_ic and m_ic.group(1) else None
        return "International_Championship", s_num, "IC"

    # 3. Intermezzo Championship
    if re.search(r'(?:\bIntermezzo(?:\s+Championship)?\b|\bIZ\b)', tournament_str, re.IGNORECASE) or re.search(r'\bIZ_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_im = re.search(r'(?:\bIntermezzo(?:\s+Championship)?\b|\bIZ)[_\s]*(?:Season|s)?_?0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_im.group(1)) if m_im and m_im.group(1) else None
        return "Intermezzo_Championship", s_num, "IZ"

    # 4. Mercurial Ladder (MANDATORY: require Season/s keyword so elemental numbers like 1-Hydrogen are not matched!)
    if re.search(r'(?:\bMercurial(?:[_\s]+Ladder)?\b|\bML\b)', tournament_str, re.IGNORECASE) or re.search(r'\bML_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_ml = re.search(r'(?:\bMercurial(?:[_\s]+Ladder)?\b|\bML)[_\s]*.*?\b(?:Season|s)[_\s]*0?(\d+)', tournament_str, re.IGNORECASE)
        if not m_ml:
            m_ml = re.search(r'\bML_s0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_ml.group(1)) if m_ml and m_ml.group(1) else None
        return "Mercurial_Ladder", s_num, "ML"

    # 5. Transcontinental Ladder
    if re.search(r'(?:\bTranscontinental(?:[_\s]+Ladder)?\b|\bTCL\b|\bTL\b)', tournament_str, re.IGNORECASE) or re.search(r'\bTCL_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_stage = re.search(r'Stage\s*0?(\d+)(?:\s+of\s+\d+)?', tournament_str, re.IGNORECASE)
        m_tl = re.search(r'(?:\bTranscontinental(?:[_\s]+Ladder)?\b|\bTCL\b|\bTL)[_\s]*(?:Round|round|Season|s)?_?0?(\d+)', tournament_str, re.IGNORECASE)
        if m_tl and int(m_tl.group(1)) > 50:
            s_num = int(m_tl.group(1))
        elif m_stage:
            cge_st = int(m_stage.group(1))
            s_num = cge_st + 54 if cge_st < 100 else cge_st
        elif m_tl:
            s_num = int(m_tl.group(1))
        else:
            s_num = None
        return "Transcontinental_Ladder", s_num, "TCL"

    # 6. Sodium Ladder (MANDATORY: only extract season if explicit Season/s keyword or SL_sNN prefix; NEVER match atomic numbers!)
    if re.search(r'(?:\bSodium(?:[_\s]+Ladder)?\b|\bSL\b)', tournament_str, re.IGNORECASE) or re.search(r'\bSL_s?0?(\d+)', tournament_str, re.IGNORECASE):
        m_sl = re.search(r'(?:\bSodium(?:[_\s]+Ladder)?\b|\bSL)[_\s]*.*?\b(?:Season|s)[_\s]*0?(\d+)', tournament_str, re.IGNORECASE)
        if not m_sl:
            m_sl = re.search(r'\bSL_s0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_sl.group(1)) if m_sl and m_sl.group(1) else None
        return "Sodium_Ladder", s_num, "SL"

    # 7. Q&D / Quick and Dirty
    if re.search(r'\b(?:Q&D|QD|Quick\s+and\s+Dirty)\b', tournament_str, re.IGNORECASE):
        m_qd = re.search(r'0?(\d+)', tournament_str)
        return "Q&D", int(m_qd.group(1)) if m_qd else None, "QD"

    # 8. Australien Open
    if re.search(r'(?:\bAussie|\bAussieOpen|\bAO\b|\bAustralian[_\s]+Open|\bAustralien[_\s]+Open)', tournament_str, re.IGNORECASE):
        m_ao = re.search(r'0?(\d+)', tournament_str)
        return "Australien_Open", int(m_ao.group(1)) if m_ao else None, "AO"

    # 9. Survivors Cup (Multi-stage)
    if re.search(r'\bSurvivors?\s+Cup\b', tournament_str, re.IGNORECASE):
        m_sc = re.search(r'\bSurvivors?\s+Cup\b.*?Stage\s*0?(\d+)', tournament_str, re.IGNORECASE)
        return "Survivors_Cup_2026", int(m_sc.group(1)) if m_sc else None, "SC"

    # 10. French Open
    if re.search(r'\bFrench\s+Open\b', tournament_str, re.IGNORECASE):
        m_fo = re.search(r'\bFrench\s+Open\b.*?Stage\s*0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_fo.group(1)) if m_fo else 1
        if "even" in tournament_str.lower():
            return "French_Open_Even", s_num, "FO_even"
        elif "odd" in tournament_str.lower():
            return "French_Open_Odd", s_num, "FO_odd"
        return "French_Open_2026", s_num, "FO"

    # 11. World Championship / Worlds (Multi-stage)
    if re.search(r'(?:\bWorld\s+Championship\b|\bWorlds\b)', tournament_str, re.IGNORECASE):
        m_wc = re.search(r'(?:\bWorld\s+Championship\b|\bWorlds\b).*?Stage\s*0?(\d+)', tournament_str, re.IGNORECASE)
        return "World_Championship_2026", int(m_wc.group(1)) if m_wc else None, "WC"

    # 12. Slow Burn (distinguish First Edition vs Second Edition)
    if re.search(r'\bSlow\s+Burn\b', tournament_str, re.IGNORECASE):
        m_sb = re.search(r'\bSlow\s+Burn\b.*?\b(?:Season|s|stage)[_\s]*0?(\d+)', tournament_str, re.IGNORECASE)
        if not m_sb:
            m_sb = re.search(r'\bSlow\s+Burn\b.*?0?(\d+)', tournament_str, re.IGNORECASE)
        s_num = int(m_sb.group(1)) if m_sb else None
        is_second = "second" in tournament_str.lower() or "edition 2" in tournament_str.lower() or "season 2" in tournament_str.lower()
        folder = "Slow_Burn_Second_Edition" if is_second else "Slow_Burn_First_Edition"
        return folder, s_num, "SB"

    # Fallback: derive clean slug from tournament string
    clean_name = re.sub(r'[^A-Za-z0-9_\-]+', '_', tournament_str.split('-')[0].strip()).strip('_')
    m_num = re.search(r'0?(\d+)', tournament_str)
    return clean_name or "Misc_Tournaments", int(m_num.group(1)) if m_num else None, clean_name[:8] or "MISC"


def save_season_matches_to_tournament_folder(
    matches: List[Dict[str, Any]],
    tournaments_dir: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Groups matches by tournament folder and season, saving/appending to dedicated season CSVs.

    Files are written to: <tournaments_dir>/<folder>/matches/<CODE>_s<NN>.csv
    e.g. Royal_League/matches/RL_s09.csv
    """
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    grouped: Dict[Tuple[str, Optional[int], str], List[Dict[str, Any]]] = {}
    for m in matches:
        folder, s_num, code = resolve_tournament_folder_and_season(m.get("tournament", ""))
        key = (folder, s_num, code)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(m)

    results = []
    for (folder, s_num, code), m_list in grouped.items():
        t_dir = base_dir / folder
        matches_dir = t_dir / "matches"
        matches_dir.mkdir(parents=True, exist_ok=True)

        if s_num is not None:
            csv_file = matches_dir / f"{code}_s{s_num:02d}.csv"
        else:
            csv_file = matches_dir / f"{code}_misc.csv"

        # Load existing keys in this season CSV to avoid duplicates
        existing_keys: set = set()
        file_exists = csv_file.exists()
        if file_exists:
            with open(csv_file, mode="r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parts = []
                    for idx in range(1, 5):
                        p_col = f"Player{idx}"
                        s_col = f"Score{idx}"
                        if p_col in row and row[p_col]:
                            p_val = row[p_col].strip()
                            s_val = float(row.get(s_col, 0) or 0)
                            parts.append((p_val, s_val))
                    if parts:
                        existing_keys.add(make_dedup_key(row.get("Tournament", ""), row.get("Date", ""), parts))

        rows_to_append = []
        for m in m_list:
            parts = m.get("participants", [])
            key = make_dedup_key(m.get("tournament", ""), m.get("date", ""), parts)
            if key not in existing_keys:
                rows_to_append.append(m)
                existing_keys.add(key)

        if rows_to_append:
            with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow([
                        "Tournament", "Date",
                        "Player1", "Score1",
                        "Player2", "Score2",
                        "Player3", "Score3",
                        "Player4", "Score4",
                        "Player_Count"
                    ])
                for m in rows_to_append:
                    parts = m["participants"]
                    p_count = len(parts)
                    p1, s1 = parts[0]
                    p2, s2 = parts[1]
                    p3 = parts[2][0] if p_count > 2 else ""
                    s3 = parts[2][1] if p_count > 2 else ""
                    p4 = parts[3][0] if p_count > 3 else ""
                    s4 = parts[3][1] if p_count > 3 else ""
                    writer.writerow([
                        m["tournament"], m["date"],
                        p1, s1, p2, s2, p3, s3, p4, s4,
                        p_count
                    ])

        results.append({
            "folder": folder,
            "season": s_num,
            "csv_code": code,
            "file": str(csv_file.relative_to(base_dir)),
            "rows_written": len(rows_to_append)
        })

    return results


CGE_MAPPINGS = {
    'international': lambda s: f" (CGE {s - 9})" if s >= 10 else "",
    'tcl': lambda r: f" (CGE {r - 54})" if r >= 55 else "",
}


def humanize_tournament_stage(tournament_str: str) -> str:
    """Converts a raw match tournament string into a clean, human-readable tournament & stage name.

    Examples:
        'French Open 2026 (Even Games) Stage 1 - group 1 game 1' -> 'French Open 2026 Stage 1 (even games)'
        'International S34 - Group A - game 1' -> 'International Championship Season 34 (CGE 25)'
        'RL_s09 - Emperor - game 1' -> 'Royal League Season 9'
        'Survivors Cup 2026 Stage 7 - group 1 game 1' -> 'Survivors Cup 2026 Stage 7'
        'TCL Round 138' -> 'Transcontinental Ladder Round 138 (CGE 84)'
        'World Championship 2026 Stage 5 - game 1' -> 'World Championship 2026 Stage 5'
    """
    s = (tournament_str or "").strip()
    if not s or "cge online" in s.lower() or "tournament does not exist" in s.lower():
        return ""

    # 1. Royal League
    m_rl = re.search(r'(?:\bRoyal[_\s]+League\b|\bRL)[_\s]*(?:Season|s)?_?0?(\d+)', s, re.IGNORECASE)
    if m_rl:
        return f"Royal League Season {int(m_rl.group(1))}"

    # 2. International Championship
    m_ic = re.search(r'(?:\bInternational(?:\s+Championship)?\b|\bIC)[_\s]*(?:Season|s)?_?0?(\d+)', s, re.IGNORECASE)
    if m_ic:
        s_num = int(m_ic.group(1))
        cge_info = CGE_MAPPINGS['international'](s_num)
        return f"International Championship Season {s_num}{cge_info}"

    # 3. Intermezzo Championship
    m_iz = re.search(r'(?:\bIntermezzo(?:\s+Championship)?\b|\bIZ)[_\s]*(?:Season|s)?_?0?(\d+)', s, re.IGNORECASE)
    if m_iz:
        return f"Intermezzo Championship Season {int(m_iz.group(1))}"

    # 4. Survivors Cup
    m_sc = re.search(r'(Survivors\s+Cup(?:\s+\d{4})?).*?Stage\s*0?(\d+)', s, re.IGNORECASE)
    if m_sc:
        return f"{m_sc.group(1)} Stage {int(m_sc.group(2))}"

    # 5. French Open
    m_fo = re.search(r'French\s+Open(?:\s+\d+)?.*?Stage\s*0?(\d+)', s, re.IGNORECASE)
    st_num = int(m_fo.group(1)) if m_fo else 1
    tag = ""
    if "even" in s.lower():
        tag = " (even games)"
    elif "odd" in s.lower():
        tag = " (odd games)"
    if m_fo or "french open" in s.lower():
        return f"French Open 2026 Stage {st_num}{tag}".strip()

    # 6. Worlds / World Championship
    m_w = re.search(r'(?:World\s+Championship|Worlds)(?:\s+\d+)?.*?stage\s*0?(\d+)', s, re.IGNORECASE)
    if m_w:
        return f"World Championship 2026 Stage {int(m_w.group(1))}"

    # 7. Mercurial Ladder
    m_ml = re.search(r'(?:\bMercurial(?:[_\s]+Ladder)?\b|\bML\b)[_\s]*.*?\b(?:Season|s)[_\s]*0?(\d+)', s, re.IGNORECASE)
    if not m_ml:
        m_ml = re.search(r'\bML_s?0?(\d+)', s, re.IGNORECASE)
    if m_ml:
        return f"Mercurial Ladder Season {int(m_ml.group(1))}"

    # 8. Sodium Ladder
    m_sl = re.search(r'(?:\bSodium(?:[_\s]+Ladder)?\b|\bSL\b)[_\s]*.*?\b(?:Season|s)[_\s]*0?(\d+)', s, re.IGNORECASE)
    if not m_sl:
        m_sl = re.search(r'\bSL_s?0?(\d+)', s, re.IGNORECASE)
    if m_sl:
        return f"Sodium Ladder Season {int(m_sl.group(1))}"

    # 9. Slow Burn (show both Edition and Season)
    m_sb = re.search(r'\bSlow[_\s]+Burn\b.*?\b(?:Season|s|stage)[_\s]*0?(\d+)', s, re.IGNORECASE)
    if not m_sb:
        m_sb = re.search(r'\bSlow[_\s]+Burn[_\s]*0?(\d+)', s, re.IGNORECASE)
    if m_sb:
        s_num = int(m_sb.group(1))
        is_second = "second" in s.lower() or "edition 2" in s.lower() or "season 2" in s.lower()
        edition = "Second Edition" if is_second else "First Edition"
        return f"Slow Burn {edition} Season {s_num}"
    elif "slow burn" in s.lower():
        is_second = "second" in s.lower() or "edition 2" in s.lower()
        edition = "Second Edition" if is_second else "First Edition"
        return f"Slow Burn {edition}"

    # 10. Transcontinental Ladder
    m_tcl_stage = re.search(r'(?:Transcontinental(?:[_\s]+Ladder)?|\bTCL\b|\bTL\b).*?Stage\s*0?(\d+)', s, re.IGNORECASE)
    if m_tcl_stage:
        cge_st = int(m_tcl_stage.group(1))
        r_num = cge_st + 54 if cge_st < 100 else cge_st
        cge_info = CGE_MAPPINGS['tcl'](r_num)
        return f"Transcontinental Ladder Round {r_num}{cge_info}"

    m_tcl = re.search(r'(?:Transcontinental(?:[_\s]+Ladder)?|\bTCL\b|\bTL\b)[_\s]*(?:Round|round|Season|s)?[_\s]*0?(\d+)', s, re.IGNORECASE)
    if m_tcl:
        r_num = int(m_tcl.group(1))
        cge_info = CGE_MAPPINGS['tcl'](r_num)
        return f"Transcontinental Ladder Round {r_num}{cge_info}"

    # 11. Australian Open
    m_ao = re.search(r'(?:Australien|Australian|Aussie)[_\s]*(?:Open)?[_\s]*0?(\d+)', s, re.IGNORECASE)
    if m_ao:
        return f"Australian Open {m_ao.group(1)}"

    # 12. Q&D
    m_qd = re.search(r'(?:Q&D|Quick\s+and\s+Dirty|QD)[_\s]*(?:Season|s)?[_\s]*0?(\d+)?', s, re.IGNORECASE)
    if m_qd and ("q&d" in s.lower() or "quick and dirty" in s.lower() or "qd" in s.lower()):
        s_num = f" Season {int(m_qd.group(1))}" if m_qd.group(1) else ""
        return f"Q&D{s_num}"

    # Clean generic fallback: strip subgroups and division names after delimiter
    clean = re.sub(r'\s*[-–—]\s*.*$', '', s).strip()
    clean = re.sub(r'[\s\-_]+game\s*\d+.*$', '', clean, flags=re.IGNORECASE).strip()
    return clean if clean and "cge online" not in clean.lower() else ""


def get_added_tournaments_summary(
    all_matches_path: Optional[Path] = None,
    t0_path: Optional[Path] = None,
    tournaments_dir: Optional[Path] = None
) -> List[str]:
    """Returns a sorted list of human-readable names for tournaments/stages added beyond the baseline."""
    base_t0 = t0_path or ALL_MATCHES_T0_CSV
    curr_all = all_matches_path or ALL_MATCHES_CSV
    t_dir = tournaments_dir or TOURNAMENTS_DIR

    added_tourney_strings = set()

    # 1. Inspect all confirmed season/stage CSVs in tournaments/matches/
    if t_dir.exists():
        for csv_path in t_dir.glob("*/matches/*.csv"):
            try:
                with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        t_str = row.get("Tournament", "").strip()
                        if t_str:
                            added_tourney_strings.add(t_str)
            except Exception:
                pass

    # 2. Inspect all_matches.csv diff against t0 if t0 exists
    if base_t0.exists() and curr_all.exists():
        try:
            with open(base_t0, mode="r", encoding="utf-8", errors="replace") as f0:
                t0_tourneys = {r.get("Tournament", "").strip() for r in csv.DictReader(f0)}
            with open(curr_all, mode="r", encoding="utf-8", errors="replace") as fa:
                for r in csv.DictReader(fa):
                    d_str = r.get("Date", "").strip()
                    if d_str and d_str < "2026-01-01":
                        continue
                    t_str = r.get("Tournament", "").strip()
                    if t_str and t_str not in t0_tourneys:
                        added_tourney_strings.add(t_str)
        except Exception:
            pass

    # Humanize and group
    humanized_map = {}
    for raw_str in added_tourney_strings:
        h_name = humanize_tournament_stage(raw_str)
        if h_name:
            humanized_map[h_name] = humanized_map.get(h_name, 0) + 1

    # Custom natural sort key
    def sort_key(name: str):
        nums = [int(n) for n in re.findall(r'\d+', name)]
        clean_prefix = re.sub(r'\d+', '', name).lower()
        return (clean_prefix, nums)

    return sorted(humanized_map.keys(), key=sort_key)


def export_update_snapshot(
    updates_dir: Optional[Path] = None,
    timestamp_str: Optional[str] = None,
    all_matches_path: Optional[Path] = None,
    tournaments_dir: Optional[Path] = None,
    new_matches: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Saves newly added tournaments summary to {timestamp}_tournaments.txt and newly scraped matches to {timestamp}_all_games.csv.
    
    Files created in data/updates/:
      - {date}_{HH-MM}_tournaments.txt  (Clean list of tournament and stages added, without any subgroups)
      - {date}_{HH-MM}_all_games.csv    (CSV containing ONLY the newly scraped/added matches from this update)
    """
    u_dir = updates_dir or UPDATES_DIR
    u_dir.mkdir(parents=True, exist_ok=True)
    t_dir = tournaments_dir or TOURNAMENTS_DIR

    now = datetime.now()
    ts = timestamp_str or now.strftime("%Y-%m-%d_%H-%M")
    txt_file = u_dir / f"{ts}_tournaments.txt"
    csv_file = u_dir / f"{ts}_all_games.csv"

    # 1. Clean tournaments summary without subgroups
    tourneys_summary = get_added_tournaments_summary(
        all_matches_path=all_matches_path,
        tournaments_dir=tournaments_dir
    )
    txt_file.write_text("\n".join(tourneys_summary) + "\n", encoding="utf-8")

    # 2. Write ONLY the newly scraped matches (delta), NOT all historical matches!
    added_rows = []
    if new_matches:
        for m in new_matches:
            added_rows.append(m)
    else:
        # Read from confirmed season files in data/tournaments/*/matches/*.csv
        if t_dir.exists():
            for s_csv in sorted(t_dir.glob("*/matches/*.csv")):
                try:
                    with open(s_csv, mode="r", encoding="utf-8", errors="replace") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            added_rows.append(row)
                except Exception:
                    pass

    # Write added matches to csv_file
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Tournament", "Date",
            "Player1", "Score1",
            "Player2", "Score2",
            "Player3", "Score3",
            "Player4", "Score4",
            "Player_Count"
        ])
        for r in added_rows:
            if isinstance(r, dict) and "participants" in r:
                parts = r.get("participants", [])
                p_cnt = len(parts)
                p1, s1 = parts[0] if p_cnt > 0 else ("", "")
                p2, s2 = parts[1] if p_cnt > 1 else ("", "")
                p3, s3 = parts[2] if p_cnt > 2 else ("", "")
                p4, s4 = parts[3] if p_cnt > 3 else ("", "")
                writer.writerow([
                    r.get("tournament", ""), r.get("date", ""),
                    p1, s1, p2, s2, p3, s3, p4, s4, p_cnt
                ])
            elif isinstance(r, dict):
                writer.writerow([
                    r.get("Tournament", ""), r.get("Date", ""),
                    r.get("Player1", ""), r.get("Score1", ""),
                    r.get("Player2", ""), r.get("Score2", ""),
                    r.get("Player3", ""), r.get("Score3", ""),
                    r.get("Player4", ""), r.get("Score4", ""),
                    r.get("Player_Count", "")
                ])

    logger.info(f"Exported update snapshot to {txt_file.name} ({len(tourneys_summary)} stages) and {csv_file.name} ({len(added_rows)} scraped rows)")
    return {
        "tournaments_file": str(txt_file),
        "all_games_file": str(csv_file),
        "tournaments_count": len(tourneys_summary),
        "tournaments": tourneys_summary,
        "scraped_matches_count": len(added_rows)
    }


def list_update_snapshots(updates_dir: Optional[Path] = None, conn = None) -> List[Dict[str, Any]]:
    """Lists all available update snapshot CSVs in chronological order with creation time (HH:MM) and metadata."""
    u_dir = updates_dir or UPDATES_DIR
    if not u_dir.exists():
        return []

    active_cfg = get_active_delta_config(conn)
    active_filename = active_cfg.get('active_snapshot_file') if active_cfg else None

    snapshots = []
    for csv_file in sorted(u_dir.glob("*_all_games.csv")):
        fname = csv_file.name
        
        # Match date & time in filename: YYYY-MM-DD_HH-MM or YYYY-MM-DD
        m_time = re.search(r'(\d{4}-\d{2}-\d{2})[_\s](\d{2})[-:](\d{2})', fname)
        if m_time:
            date_str = m_time.group(1)
            time_str = f"{m_time.group(2)}:{m_time.group(3)}"
            display_time = f"{date_str} {time_str}"
        else:
            m_date = re.match(r'(\d{4}-\d{2}-\d{2})', fname)
            file_mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)
            date_str = m_date.group(1) if m_date else file_mtime.strftime("%Y-%m-%d")
            time_str = file_mtime.strftime("%H:%M")
            display_time = f"{date_str} {time_str}"

        # Read line count and date bounds quickly
        match_count = 0
        min_date = None
        max_date = None
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline().strip().split(',')
                date_idx = header.index('Date') if 'Date' in header else 1
                for line in f:
                    if line.strip():
                        match_count += 1
                        parts = line.split(',')
                        if len(parts) > date_idx:
                            d = parts[date_idx].strip()
                            if re.match(r'^\d{4}-\d{2}-\d{2}', d):
                                d_sub = d[:10]
                                if min_date is None or d_sub < min_date:
                                    min_date = d_sub
                                if max_date is None or d_sub > max_date:
                                    max_date = d_sub
        except Exception:
            pass

        # Check for matching tournaments.txt (by exact prefix or date)
        base_prefix = fname.replace("_all_games.csv", "")
        txt_file = u_dir / f"{base_prefix}_tournaments.txt"
        if not txt_file.exists():
            txt_file = u_dir / f"{date_str}_tournaments.txt"
        has_summary = txt_file.exists()

        active_files = [f.strip() for f in (active_filename or "").split(",") if f.strip()]
        is_active = (fname in active_files)

        snapshots.append({
            "filename": fname,
            "date": date_str,
            "time": time_str,
            "display_time": display_time,
            "match_count": match_count,
            "min_date": min_date or "N/A",
            "max_date": max_date or "N/A",
            "size_kb": round(csv_file.stat().st_size / 1024, 1),
            "has_summary": has_summary,
            "is_active": is_active
        })

    return sorted(snapshots, key=lambda s: (s["date"], s["time"]))


def set_active_delta_snapshot(snapshot_filenames: Union[str, List[str]], conn = None) -> Dict[str, Any]:
    """Sets one or multiple snapshot CSVs as the active baseline for rating deltas, establishing the max delta timeframe."""
    from src.data.db import get_connection
    c = conn or get_connection()
    try:
        if isinstance(snapshot_filenames, str):
            filenames = [f.strip() for f in snapshot_filenames.split(",") if f.strip()]
        else:
            filenames = list(snapshot_filenames)

        if not filenames:
            return {"status": "error", "message": "No snapshots selected."}

        u_dir = UPDATES_DIR
        cutoff_dates = []

        for fn in filenames:
            m_date = re.match(r'(\d{4}-\d{2}-\d{2})', fn)
            if m_date:
                cutoff_dates.append(m_date.group(1))

        # Establish max possible delta by choosing earliest cutoff date among selected files
        earliest_cutoff = min(cutoff_dates) if cutoff_dates else None
        joined_filenames = ", ".join(filenames)

        with c:
            c.execute("""
                INSERT INTO delta_config (id, active_snapshot_file, cutoff_date, description, updated_at)
                VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    active_snapshot_file = excluded.active_snapshot_file,
                    cutoff_date = excluded.cutoff_date,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
            """, (joined_filenames, earliest_cutoff, f"Snapshots: {joined_filenames} (Max Delta Cutoff: {earliest_cutoff})"))

        return {
            "status": "success",
            "active_snapshot": joined_filenames,
            "active_snapshots": filenames,
            "cutoff_date": earliest_cutoff
        }
    finally:
        if not conn:
            c.close()


def get_active_delta_config(conn = None) -> Optional[Dict[str, Any]]:
    """Gets the currently active delta baseline configuration."""
    from src.data.db import get_connection
    c = conn or get_connection()
    try:
        row = c.execute("SELECT active_snapshot_file, cutoff_date, description, updated_at FROM delta_config WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return None
    except Exception:
        return None
    finally:
        if not conn:
            c.close()


def delete_update_snapshot(snapshot_filename: str, updates_dir: Optional[Path] = None) -> bool:
    """Deletes an update snapshot and its corresponding summary file."""
    u_dir = updates_dir or UPDATES_DIR
    csv_file = u_dir / snapshot_filename
    if csv_file.exists():
        csv_file.unlink()
        base_prefix = snapshot_filename.replace("_all_games.csv", "")
        txt_file = u_dir / f"{base_prefix}_tournaments.txt"
        if txt_file.exists():
            txt_file.unlink()
        else:
            m_date = re.match(r'(\d{4}-\d{2}-\d{2})', snapshot_filename)
            if m_date:
                txt_date = u_dir / f"{m_date.group(1)}_tournaments.txt"
                if txt_date.exists():
                    txt_date.unlink()
        return True
    return False



