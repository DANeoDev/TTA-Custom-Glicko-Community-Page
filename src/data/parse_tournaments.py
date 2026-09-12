"""Ingestion and aggregation of competitive TTA tournament archives and match campaigns into SQLite."""
import os
import re
import csv
import json
import sqlite3
from pathlib import Path
import openpyxl

DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
TOURNAMENTS_DIR = DATA_DIR / 'tournaments'
DB_PATH = DATA_DIR / 'tta_ratings.db'

# Known official tournament finish dates
INTL_DATES = {
    34: "2026-08-14", 33: "2026-05-08", 32: "2026-01-28", 31: "2025-10-29",
    30: "2025-08-14", 29: "2025-05-12", 28: "2025-02-12", 27: "2024-09-04",
    26: "2024-06-02", 25: "2024-03-03", 24: "2023-12-03", 23: "2023-09-03",
    22: "2023-06-04", 21: "2023-02-05", 20: "2022-12-04", 19: "2022-09-04",
    18: "2022-06-05", 17: "2022-03-06", 16: "2021-12-05", 15: "2021-09-05",
    14: "2021-06-02", 13: "2021-03-02", 12: "2020-12-06", 11: "2020-09-27",
    10: "2020-06-28", 9: "2020-03-30", 8: "2019-12-30", 7: "2019-09-30",
    6: "2019-05-26", 5: "2019-02-17", 4: "2018-10-14", 3: "2018-06-17",
    2: "2017-11-17", 1: "2017-06-15"
}

INTER_DATES = {
    31: "2026-08-15", 30: "2026-05-31", 29: "2026-02-28", 28: "2025-11-30",
    27: "2025-09-17", 26: "2025-05-31", 25: "2025-02-28", 24: "2024-08-31",
    23: "2024-05-31", 22: "2024-02-29", 21: "2023-11-30", 20: "2023-08-31",
    19: "2023-05-31", 18: "2023-02-28", 17: "2022-11-30", 16: "2022-08-31",
    15: "2022-05-31", 14: "2022-02-28", 13: "2021-11-30", 12: "2021-09-10",
    11: "2021-05-31", 10: "2021-02-28", 9: "2020-11-30", 8: "2020-08-31",
    7: "2020-05-31", 6: "2020-05-10", 5: "2020-02-09", 4: "2019-11-10",
    3: "2019-08-04", 2: "2019-06-23", 1: "2019-03-24"
}

RL_DATES = {
    8: "2026-05-27", 7: "2026-02-27", 6: "2025-11-30", 5: "2025-08-31",
    4: "2025-05-30", 3: "2025-02-28", 2: "2024-10-31", 1: "2024-08-11"
}


def get_finish_date(tourney, season, fallback_date="2026-01-01"):
    t_str = str(tourney)
    s_str = str(season)
    if "International" in t_str:
        m = re.search(r'Season\s+(\d+)', s_str)
        if m and int(m.group(1)) in INTL_DATES:
            return INTL_DATES[int(m.group(1))]
    elif "Intermezzo" in t_str:
        m = re.search(r'Season\s+(\d+)', s_str)
        if m and int(m.group(1)) in INTER_DATES:
            return INTER_DATES[int(m.group(1))]
    elif "Royal League" in t_str:
        m = re.search(r'Season\s+(\d+)', s_str)
        if m and int(m.group(1)) in RL_DATES:
            return RL_DATES[int(m.group(1))]
        if "2026 Q2" in s_str: return "2026-05-27"
        if "2026 Q1" in s_str: return "2026-02-27"
        if "2025 Q4" in s_str: return "2025-11-30"
        if "2025 Q3" in s_str: return "2025-08-31"
        if "2025 Q2" in s_str: return "2025-05-30"
        if "2025 Q1" in s_str: return "2025-02-28"
        if "2024 Q4" in s_str: return "2024-11-30"
        if "2024 Q3" in s_str: return "2024-08-11"
    elif "Aussie" in t_str:
        return "2026-03-15"
    return fallback_date or "2026-01-01"


def normalize_campaign(tourney_str):
    if not tourney_str:
        return ("Unknown Tournament", "Season", "Main")
    s = tourney_str.strip()
    s = re.sub(r'[\s\-_]+game\s*\d+.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[\s\-_]+g\d+.*$', '', s, flags=re.IGNORECASE)
    s = s.strip(' -_')

    m_intl = re.match(r'International\s+S(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_intl:
        s_num = m_intl.group(1)
        div = m_intl.group(2) or "Grandmaster"
        return ("International Championship", f"Season {s_num}", div)

    m_inter = re.match(r'Intermezzo\s+S(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_inter:
        s_num = m_inter.group(1)
        div = m_inter.group(2) or "Grandmaster"
        return ("Intermezzo Championship", f"Season {s_num}", div)

    m_rl = re.match(r'RL_s0?(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_rl:
        s_num = m_rl.group(1)
        div = m_rl.group(2) or "Division"
        return ("Royal League", f"Season {s_num}", div)

    m_w = re.match(r'Worlds\s+(\d+)(?:\s*[-–]\s*)?(stage\s*\d+)?(?:\s*[-–]\s*(.*))?', s, re.IGNORECASE)
    if m_w:
        w_year = m_w.group(1)
        stage = m_w.group(2) or "Championship"
        div = m_w.group(3) or stage
        return (f"World Championship {w_year}", stage.title(), div)

    m_merc = re.match(r'Mercurial\s+Season\s+(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_merc:
        s_num = m_merc.group(1)
        div = m_merc.group(2) or "Ladder Division"
        return ("Mercurial Ladder", f"Season {s_num}", div)

    m_sod = re.match(r'Sodium\s+Season\s+(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_sod:
        s_num = m_sod.group(1)
        div = m_sod.group(2) or "Ladder Division"
        return ("Sodium Ladder", f"Season {s_num}", div)

    m_eff = re.match(r'Eiffel\s+Tower\s+S(\d+)(?:\s*-\s*(.*))?', s, re.IGNORECASE)
    if m_eff:
        s_num = m_eff.group(1)
        div = m_eff.group(2) or "Division"
        return ("Eiffel Tower Cup", f"Season {s_num}", div)

    parts = [p.strip() for p in s.split(' - ') if p.strip()]
    if len(parts) >= 2:
        return (parts[0], parts[1], parts[2] if len(parts) > 2 else "Main")
    return (s, "Tournament", "Main")


def normalize_name(name, canonical_map):
    """Normalize player name against canonical database names (case-insensitive)."""
    if not name:
        return None
    cleaned = str(name).strip()
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned).strip()
    cleaned = cleaned.replace('🇳🇴', '').replace('🇫🇷', '').replace('🇩🇪', '')
    cleaned = cleaned.replace('🇨🇳', '').replace('🇧🇪', '').replace('🇷🇺', '')
    cleaned = cleaned.replace('🇦🇺', '').replace('🇰🇷', '').replace('🇺🇦', '')
    cleaned = cleaned.replace('🇨🇿', '').replace('🇨🇦', '').replace('🇧🇷', '')
    cleaned = cleaned.replace('🇸🇰', '').strip()
    return canonical_map.get(cleaned.lower(), cleaned)


def parse_all_tournaments(db_path=None):
    db_file = db_path or DB_PATH
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # Drop & recreate tables to support finish_date & is_career_total
    with conn:
        conn.execute("DROP TABLE IF EXISTS player_achievements;")
        conn.execute("DROP TABLE IF EXISTS tournament_records;")
        conn.execute("""
            CREATE TABLE player_achievements (
                player_name TEXT PRIMARY KEY,
                total_titles INTEGER DEFAULT 0,
                international_titles INTEGER DEFAULT 0,
                intermezzo_titles INTEGER DEFAULT 0,
                royal_league_titles INTEGER DEFAULT 0,
                other_titles INTEGER DEFAULT 0,
                gold_medals INTEGER DEFAULT 0,
                silver_medals INTEGER DEFAULT 0,
                bronze_medals INTEGER DEFAULT 0,
                summary_text TEXT,
                top_achievements_json TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE tournament_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                tournament_name TEXT NOT NULL,
                season TEXT,
                division TEXT,
                placement TEXT,
                points TEXT,
                medal TEXT,
                details TEXT,
                finish_date TEXT,
                is_career_total INTEGER DEFAULT 0
            );
        """)
        conn.execute("CREATE INDEX idx_tr_player ON tournament_records(player_name);")
        conn.execute("CREATE INDEX idx_tr_tourney ON tournament_records(tournament_name);")
        conn.execute("CREATE INDEX idx_tr_finish ON tournament_records(finish_date);")

    # Load canonical player mapping
    canonical_map = {}
    for row in conn.execute("SELECT name FROM players"):
        pname = row['name']
        canonical_map[pname.lower()] = pname

    records = []
    # Index to quickly lookup existing official records: (player_name, tournament_name, season) -> record_dict
    official_rec_idx = {}
    player_stats = {}

    def get_stats(pname):
        if pname not in player_stats:
            player_stats[pname] = {
                'player_name': pname,
                'total_titles': 0,
                'international_titles': 0,
                'intermezzo_titles': 0,
                'royal_league_titles': 0,
                'other_titles': 0,
                'gold_medals': 0,
                'silver_medals': 0,
                'bronze_medals': 0,
                'top_achievements': [],
                'seasons_intl': 0,
                'points_intl': 0.0,
                'seasons_inter': 0,
                'points_inter': 0.0,
            }
        return player_stats[pname]

    # 1. Parse Hall of Fame.xlsx
    hof_path = TOURNAMENTS_DIR / 'Hall of Fame.xlsx'
    if hof_path.exists():
        wb = openpyxl.load_workbook(str(hof_path), data_only=True)

        # 1a. International Championship
        if 'International Championship' in wb.sheetnames:
            ws = wb['International Championship']
            for row in ws.iter_rows(min_row=2, values_only=True):
                raw_name = row[3] if len(row) > 3 else None
                if not raw_name or 'ordered by' in str(raw_name).lower() or '*' in str(raw_name):
                    continue
                pname = normalize_name(raw_name, canonical_map)
                winner = int(row[5]) if len(row) > 5 and row[5] is not None and str(row[5]).replace('.','',1).isdigit() else 0
                runner_up = int(row[6]) if len(row) > 6 and row[6] is not None and str(row[6]).replace('.','',1).isdigit() else 0
                third = int(row[7]) if len(row) > 7 and row[7] is not None and str(row[7]).replace('.','',1).isdigit() else 0
                points = float(row[8]) if len(row) > 8 and row[8] is not None and str(row[8]).replace('.','',1).isdigit() else 0.0
                seasons = int(row[9]) if len(row) > 9 and row[9] is not None and str(row[9]).replace('.','',1).isdigit() else 0

                st = get_stats(pname)
                st['international_titles'] += winner
                st['total_titles'] += winner
                st['gold_medals'] += winner
                st['silver_medals'] += runner_up
                st['bronze_medals'] += third
                st['seasons_intl'] = seasons
                st['points_intl'] = points

                if winner > 0:
                    st['top_achievements'].append(f"{winner}x International Champion")
                if runner_up > 0:
                    st['top_achievements'].append(f"{runner_up}x International Runner-up")
                if third > 0 and winner == 0:
                    st['top_achievements'].append(f"{third}x International 3rd Place")

                # Career record
                c_rec = {
                    'player_name': pname,
                    'tournament_name': 'International Championship',
                    'season': f'Career ({seasons} seasons)',
                    'division': 'Grandmaster / Hall of Fame',
                    'placement': f'{winner}x 1st, {runner_up}x 2nd, {third}x 3rd',
                    'points': f'{points:g} pts',
                    'medal': 'gold' if winner > 0 else ('silver' if runner_up > 0 else ('bronze' if third > 0 else '')),
                    'details': f'Participated in {seasons} seasons, total score: {points:g} pts',
                    'finish_date': 'Career / All-Time',
                    'is_career_total': 1
                }
                records.append(c_rec)

                # Individual seasons
                for col_idx in range(11, min(len(row), 44)):
                    season_val = row[col_idx]
                    if season_val is not None and str(season_val).strip() not in ('', '*', '-'):
                        s_num = col_idx - 8
                        s_date = INTL_DATES.get(s_num, "2026-01-01")
                        s_rec = {
                            'player_name': pname,
                            'tournament_name': 'International Championship',
                            'season': f'Season {s_num}',
                            'division': 'Competitive Division',
                            'placement': f'{season_val} pts finish',
                            'points': f'{season_val} pts',
                            'medal': 'gold' if str(season_val) in ('28', '28.0', '30', '30.0', '36', '36.0') else '',
                            'details': f'Season {s_num} International Championship Standing',
                            'finish_date': s_date,
                            'is_career_total': 0
                        }
                        records.append(s_rec)
                        official_rec_idx[(pname, 'International Championship', f'Season {s_num}')] = s_rec

        # 1b. Intermezzo Championship
        if 'Intermezzo Championship' in wb.sheetnames:
            ws = wb['Intermezzo Championship']
            for row in ws.iter_rows(min_row=2, values_only=True):
                raw_name = row[3] if len(row) > 3 else None
                if not raw_name or 'ordered by' in str(raw_name).lower() or '*' in str(raw_name):
                    continue
                pname = normalize_name(raw_name, canonical_map)
                winner = int(row[5]) if len(row) > 5 and row[5] is not None and str(row[5]).replace('.','',1).isdigit() else 0
                runner_up = int(row[6]) if len(row) > 6 and row[6] is not None and str(row[6]).replace('.','',1).isdigit() else 0
                third = int(row[7]) if len(row) > 7 and row[7] is not None and str(row[7]).replace('.','',1).isdigit() else 0
                points = float(row[8]) if len(row) > 8 and row[8] is not None and str(row[8]).replace('.','',1).isdigit() else 0.0
                seasons = int(row[9]) if len(row) > 9 and row[9] is not None and str(row[9]).replace('.','',1).isdigit() else 0

                st = get_stats(pname)
                st['intermezzo_titles'] += winner
                st['total_titles'] += winner
                st['gold_medals'] += winner
                st['silver_medals'] += runner_up
                st['bronze_medals'] += third
                st['seasons_inter'] = seasons
                st['points_inter'] = points

                if winner > 0:
                    st['top_achievements'].append(f"{winner}x Intermezzo Champion")
                if runner_up > 0:
                    st['top_achievements'].append(f"{runner_up}x Intermezzo Runner-up")
                if third > 0 and winner == 0:
                    st['top_achievements'].append(f"{third}x Intermezzo 3rd Place")

                c_rec = {
                    'player_name': pname,
                    'tournament_name': 'Intermezzo Championship',
                    'season': f'Career ({seasons} seasons)',
                    'division': 'Hall of Fame',
                    'placement': f'{winner}x 1st, {runner_up}x 2nd, {third}x 3rd',
                    'points': f'{points:g} pts',
                    'medal': 'gold' if winner > 0 else ('silver' if runner_up > 0 else ('bronze' if third > 0 else '')),
                    'details': f'Participated in {seasons} seasons, total score: {points:g} pts',
                    'finish_date': 'Career / All-Time',
                    'is_career_total': 1
                }
                records.append(c_rec)

                for col_idx in range(11, min(len(row), 42)):
                    season_val = row[col_idx]
                    if season_val is not None and str(season_val).strip() not in ('', '*', '-'):
                        s_num = col_idx - 10
                        s_date = INTER_DATES.get(s_num, "2026-01-01")
                        s_rec = {
                            'player_name': pname,
                            'tournament_name': 'Intermezzo Championship',
                            'season': f'Season {s_num}',
                            'division': 'Competitive Division',
                            'placement': f'{season_val} pts finish',
                            'points': f'{season_val} pts',
                            'medal': '',
                            'details': f'Season {s_num} Intermezzo Standing',
                            'finish_date': s_date,
                            'is_career_total': 0
                        }
                        records.append(s_rec)
                        official_rec_idx[(pname, 'Intermezzo Championship', f'Season {s_num}')] = s_rec

    # 2. Parse Royal League
    rl_md_path = TOURNAMENTS_DIR / 'Royal_League' / 'royal_league.md'
    if rl_md_path.exists():
        with open(rl_md_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        hof_match = re.search(r'Season\s+Gold[^\n]*\n(.*?)(?:\n\s*\n|Full Results)', content, re.DOTALL)
        if hof_match:
            for line in hof_match.group(1).strip().split('\n'):
                parts = [p.strip() for p in line.split('\t') if p.strip()]
                if len(parts) >= 2:
                    season_name = parts[0]
                    golds = [normalize_name(x, canonical_map) for x in parts[1].split(',') if x.strip()]
                    silvers = [normalize_name(x, canonical_map) for x in parts[2].split(',') if x.strip()] if len(parts) > 2 else []
                    bronzes = [normalize_name(x, canonical_map) for x in parts[3].split(',') if x.strip()] if len(parts) > 3 else []

                    s_date = get_finish_date('Royal League', season_name, '2026-01-01')

                    for g in golds:
                        st = get_stats(g)
                        st['royal_league_titles'] += 1
                        st['total_titles'] += 1
                        st['gold_medals'] += 1
                        st['top_achievements'].append(f"Royal League Champion ({season_name})")
                        rec = {
                            'player_name': g,
                            'tournament_name': 'Royal League',
                            'season': season_name,
                            'division': 'Emperor',
                            'placement': '1st (Champion)',
                            'points': 'Gold Medal',
                            'medal': 'gold',
                            'details': f'Royal League Emperor Division Winner ({season_name})',
                            'finish_date': s_date,
                            'is_career_total': 0
                        }
                        records.append(rec)
                        official_rec_idx[(g, 'Royal League', season_name)] = rec

                    for s in silvers:
                        st = get_stats(s)
                        st['silver_medals'] += 1
                        st['top_achievements'].append(f"Royal League Silver Medalist ({season_name})")
                        rec = {
                            'player_name': s,
                            'tournament_name': 'Royal League',
                            'season': season_name,
                            'division': 'Emperor',
                            'placement': '2nd (Runner-up)',
                            'points': 'Silver Medal',
                            'medal': 'silver',
                            'details': f'Royal League Emperor Division Runner-up ({season_name})',
                            'finish_date': s_date,
                            'is_career_total': 0
                        }
                        records.append(rec)
                        official_rec_idx[(s, 'Royal League', season_name)] = rec

                    for b in bronzes:
                        st = get_stats(b)
                        st['bronze_medals'] += 1
                        st['top_achievements'].append(f"Royal League Bronze Medalist ({season_name})")
                        rec = {
                            'player_name': b,
                            'tournament_name': 'Royal League',
                            'season': season_name,
                            'division': 'Emperor',
                            'placement': '3rd Place',
                            'points': 'Bronze Medal',
                            'medal': 'bronze',
                            'details': f'Royal League Emperor Division 3rd Place ({season_name})',
                            'finish_date': s_date,
                            'is_career_total': 0
                        }
                        records.append(rec)
                        official_rec_idx[(b, 'Royal League', season_name)] = rec

    # 3. Parse Royal League S1 CSV
    rl_s1_csv = TOURNAMENTS_DIR / 'Royal_League' / 'TtA Royal League - S_01.csv'
    if rl_s1_csv.exists():
        with open(rl_s1_csv, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 5 and row[0].isdigit():
                    raw_name = row[2].strip()
                    div_name = row[1].strip()
                    placement = row[0].strip()
                    points = row[3].strip() if len(row) > 3 else ''
                    pname = normalize_name(raw_name, canonical_map)
                    if pname:
                        st = get_stats(pname)
                        if placement == '1':
                            st['royal_league_titles'] += 1
                            st['total_titles'] += 1
                            st['gold_medals'] += 1
                            st['top_achievements'].append(f"Royal League Season 1 {div_name} Champion")
                        elif placement == '2':
                            st['silver_medals'] += 1
                        elif placement == '3':
                            st['bronze_medals'] += 1

                        rec = {
                            'player_name': pname,
                            'tournament_name': 'Royal League',
                            'season': 'Season 1',
                            'division': div_name,
                            'placement': f'{placement} Place',
                            'points': f'{points} pts' if points else '',
                            'medal': 'gold' if placement == '1' and div_name.lower() == 'emperor' else ('silver' if placement == '2' and div_name.lower() == 'emperor' else ('bronze' if placement == '3' and div_name.lower() == 'emperor' else '')),
                            'details': f'Royal League Season 1 - {div_name} (Rank #{placement})',
                            'finish_date': '2024-08-11',
                            'is_career_total': 0
                        }
                        records.append(rec)
                        official_rec_idx[(pname, 'Royal League', 'Season 1')] = rec

    # 4. Parse Sodium Ladder
    sl_csv = TOURNAMENTS_DIR / 'Sodium_Ladder' / 'TtA Sodium Ladder - Hall of Fame.csv'
    if sl_csv.exists():
        with open(sl_csv, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('player')
                if raw_name:
                    pname = normalize_name(raw_name, canonical_map)
                    def _to_int(v):
                        try:
                            return int(float(str(v).strip().replace(',', '.')))
                        except Exception:
                            return 0
                    t1_wins = _to_int(row.get('T1 wins', 0))
                    t1_2nd = _to_int(row.get("T1 2nd's (untied)", 0))
                    inc_tax = row.get('income_tax', '')
                    st = get_stats(pname)
                    st['other_titles'] += t1_wins
                    st['total_titles'] += t1_wins
                    st['gold_medals'] += t1_wins
                    st['silver_medals'] += t1_2nd
                    if t1_wins > 0:
                        st['top_achievements'].append(f"{t1_wins}x Sodium Ladder Tier 1 Winner")
                    records.append({
                        'player_name': pname,
                        'tournament_name': 'Sodium Ladder',
                        'season': 'Career Hall of Fame',
                        'division': 'Tier 1',
                        'placement': f'{t1_wins} Titles, {t1_2nd} Runner-ups',
                        'points': f'{inc_tax} income tax pts' if inc_tax else '',
                        'medal': 'gold' if t1_wins > 0 else ('silver' if t1_2nd > 0 else ''),
                        'details': f'Sodium Ladder Career Standings: {t1_wins} T1 wins, {t1_2nd} 2nd places',
                        'finish_date': 'Career / All-Time',
                        'is_career_total': 1
                    })

    # 5. Parse Mercurial Ladder
    ml_csv = TOURNAMENTS_DIR / 'mercurial_ladder' / 'TtA Mercurial Ladder - Hall of Fame.csv'
    if ml_csv.exists():
        with open(ml_csv, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('player')
                if raw_name:
                    pname = normalize_name(raw_name, canonical_map)
                    def _to_int(v):
                        try:
                            return int(float(str(v).strip().replace(',', '.')))
                        except Exception:
                            return 0
                    prem_wins = _to_int(row.get('Premium wins', 0))
                    st = get_stats(pname)
                    st['other_titles'] += prem_wins
                    st['total_titles'] += prem_wins
                    st['gold_medals'] += prem_wins
                    if prem_wins > 0:
                        st['top_achievements'].append(f"{prem_wins}x Mercurial Ladder Premium Champion")
                    records.append({
                        'player_name': pname,
                        'tournament_name': 'Mercurial Ladder',
                        'season': 'Career Hall of Fame',
                        'division': 'Premium Tier 1',
                        'placement': f'{prem_wins} Championships',
                        'points': f'{prem_wins} Titles',
                        'medal': 'gold' if prem_wins > 0 else '',
                        'details': f'Mercurial Ladder Career: {prem_wins} Premium Tier 1 wins',
                        'finish_date': 'Career / All-Time',
                        'is_career_total': 1
                    })

    # 6. Parse Q&D Hall of Fame
    qd_csv = TOURNAMENTS_DIR / 'Q&D' / 'Quick and Dirty - Hall of Fame.csv'
    if qd_csv.exists():
        with open(qd_csv, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 12:
                    raw_name = row[8].strip()
                    g_str = row[9].strip()
                    s_str = row[10].strip()
                    b_str = row[11].strip()
                    if raw_name and raw_name.lower() not in ('player', 'name', ''):
                        if g_str.isdigit() or s_str.isdigit() or b_str.isdigit():
                            pname = normalize_name(raw_name, canonical_map)
                            g = int(g_str) if g_str.isdigit() else 0
                            s = int(s_str) if s_str.isdigit() else 0
                            b = int(b_str) if b_str.isdigit() else 0
                            st = get_stats(pname)
                            st['other_titles'] += g
                            st['total_titles'] += g
                            st['gold_medals'] += g
                            st['silver_medals'] += s
                            st['bronze_medals'] += b
                            if g > 0:
                                st['top_achievements'].append(f"{g}x Quick & Dirty Tournament Champion")
                            records.append({
                                'player_name': pname,
                                'tournament_name': 'Quick and Dirty (Q&D)',
                                'season': 'Career Trophy Hall of Fame',
                                'division': 'Championship',
                                'placement': f'{g} Gold, {s} Silver, {b} Bronze',
                                'points': f'{g+s+b} Medals',
                                'medal': 'gold' if g > 0 else ('silver' if s > 0 else ('bronze' if b > 0 else '')),
                                'details': f'Q&D Hall of Fame Medalist: {g}x Gold, {s}x Silver, {b}x Bronze',
                                'finish_date': 'Career / All-Time',
                                'is_career_total': 1
                            })

    # 7. Parse Australian Open 2026
    ao_csv = TOURNAMENTS_DIR / 'Australien_Open' / 'Aussie Open 2026 - AussieOpen2026.csv'
    if ao_csv.exists():
        with open(ao_csv, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 6 and row[0].isdigit():
                    raw_name = row[1].strip()
                    seed = row[0].strip()
                    r2_qual = row[5].strip() if len(row) > 5 else ''
                    pname = normalize_name(raw_name, canonical_map)
                    if pname:
                        st = get_stats(pname)
                        is_qual = 'yes' in r2_qual.lower() or 'true' in r2_qual.lower()
                        if is_qual:
                            st['silver_medals'] += 1
                            st['top_achievements'].append(f"Australian Open 2026 Round 2 Qualifier (Seed #{seed})")

                        rec = {
                            'player_name': pname,
                            'tournament_name': 'Australian Open',
                            'season': '2026',
                            'division': 'Main Bracket',
                            'placement': f'Round 2 Qualifier (Seed #{seed})' if is_qual else f'Group Stage (Seed #{seed})',
                            'points': 'Round 2' if is_qual else 'Group Stage',
                            'medal': 'silver' if is_qual else '',
                            'details': f'Australian Open 2026 Seed #{seed}' + (' - Qualified for Round 2' if is_qual else ''),
                            'finish_date': '2026-03-15',
                            'is_career_total': 0
                        }
                        records.append(rec)
                        official_rec_idx[(pname, 'Australian Open', '2026')] = rec

    # 8. EXTRACT ALL TOURNAMENT CAMPAIGNS FROM MATCHES TABLE
    print("Aggregating tournament match campaigns from matches table...")
    match_rows = conn.execute("""
        SELECT tournament, date, player1, score1, player2, score2, player3, score3, player4, score4, player_count
        FROM matches
    """).fetchall()

    player_campaigns = {}
    for row in match_rows:
        t_raw, m_date, p1, sc1, p2, sc2, p3, sc3, p4, sc4, p_cnt = row
        t_name, s_name, div_name = normalize_campaign(t_raw)

        players = [p1, p2, p3, p4][:p_cnt]
        scores = [sc1, sc2, sc3, sc4][:p_cnt]
        max_sc = max((s for s in scores if s is not None), default=0)

        for p, sc in zip(players, scores):
            if not p:
                continue
            pname = canonical_map.get(p.strip().lower(), p.strip())
            is_win = 1 if sc is not None and sc >= max_sc else 0

            c_key = (pname, t_name, s_name)
            if c_key not in player_campaigns:
                player_campaigns[c_key] = {
                    'division': div_name,
                    'games': 0,
                    'wins': 0,
                    'finish_date': m_date
                }
            c_entry = player_campaigns[c_key]
            c_entry['games'] += 1
            c_entry['wins'] += is_win
            if m_date > c_entry['finish_date']:
                c_entry['finish_date'] = m_date
                c_entry['division'] = div_name

    # Merge match campaigns with existing official records or add new ones
    for (pname, t_name, s_name), stats in player_campaigns.items():
        st = get_stats(pname)
        g = stats['games']
        w = stats['wins']
        l = g - w
        wr = round(w / max(1, g) * 100.0, 1)
        f_date = get_finish_date(t_name, s_name, stats['finish_date'])

        if (pname, t_name, s_name) in official_rec_idx:
            exist = official_rec_idx[(pname, t_name, s_name)]
            if stats['division'] and stats['division'] != 'Main':
                exist['division'] = stats['division']
            exist['details'] = f"{exist['details']} &bull; Record: {w}W - {l}L ({wr}% win rate)"
            if exist['finish_date'] == '2026-01-01' or not exist['finish_date']:
                exist['finish_date'] = f_date
        else:
            rec = {
                'player_name': pname,
                'tournament_name': t_name,
                'season': s_name,
                'division': stats['division'],
                'placement': f"{w}W - {l}L ({wr}%)",
                'points': f"{wr}% WR",
                'medal': 'gold' if wr >= 80.0 and g >= 6 else ('silver' if wr >= 65.0 and g >= 6 else ''),
                'details': f"Competed in {stats['division']}: {g} matches played, {w} victories ({wr}% win rate)",
                'finish_date': f_date,
                'is_career_total': 0
            }
            records.append(rec)

    # Finalize summary texts for player_achievements
    for pname, st in player_stats.items():
        titles_won = []
        if st['international_titles'] > 0:
            titles_won.append(f"{st['international_titles']} International Championship{'s' if st['international_titles'] > 1 else ''}")
        if st['intermezzo_titles'] > 0:
            titles_won.append(f"{st['intermezzo_titles']} Intermezzo Championship{'s' if st['intermezzo_titles'] > 1 else ''}")
        if st['royal_league_titles'] > 0:
            titles_won.append(f"{st['royal_league_titles']} Royal League Title{'s' if st['royal_league_titles'] > 1 else ''}")
        if st['other_titles'] > 0:
            titles_won.append(f"{st['other_titles']} Ladder/Special Tournament Title{'s' if st['other_titles'] > 1 else ''}")

        total_podiums = st['gold_medals'] + st['silver_medals'] + st['bronze_medals']

        if titles_won:
            narrative = f"{pname} is a premier competitor with {', '.join(titles_won)}, amassing {total_podiums} career podium finishes."
        elif total_podiums > 0:
            podium_details = []
            if st['silver_medals'] > 0:
                podium_details.append(f"{st['silver_medals']} silver medal{'s' if st['silver_medals'] > 1 else ''}")
            if st['bronze_medals'] > 0:
                podium_details.append(f"{st['bronze_medals']} bronze medal{'s' if st['bronze_medals'] > 1 else ''}")
            narrative = f"{pname} has earned {', '.join(podium_details)} across elite tournament competitions."
        elif st['seasons_intl'] > 0 or st['seasons_inter'] > 0:
            seasons = max(st['seasons_intl'], st['seasons_inter'])
            narrative = f"{pname} is a seasoned veteran with {seasons} registered championship seasons."
        else:
            narrative = f"{pname} is an active competitor across official Through the Ages leagues and ladders."

        st['summary_text'] = narrative

    print(f"Persisting {len(player_stats)} player achievements and {len(records)} tournament records...")
    with conn:
        for st in player_stats.values():
            conn.execute("""
                INSERT INTO player_achievements (
                    player_name, total_titles, international_titles, intermezzo_titles,
                    royal_league_titles, other_titles, gold_medals, silver_medals,
                    bronze_medals, summary_text, top_achievements_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                st['player_name'],
                st['total_titles'],
                st['international_titles'],
                st['intermezzo_titles'],
                st['royal_league_titles'],
                st['other_titles'],
                st['gold_medals'],
                st['silver_medals'],
                st['bronze_medals'],
                st['summary_text'],
                json.dumps(st['top_achievements'])
            ))

        conn.executemany("""
            INSERT INTO tournament_records (
                player_name, tournament_name, season, division, placement, points, medal, details, finish_date, is_career_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                rec['player_name'],
                rec['tournament_name'],
                rec['season'],
                rec['division'],
                rec['placement'],
                rec['points'],
                rec['medal'],
                rec['details'],
                rec.get('finish_date', '2026-01-01'),
                rec.get('is_career_total', 0)
            ) for rec in records
        ])

    conn.close()
    print(f"Successfully ingested {len(player_stats)} player achievement summaries and {len(records)} tournament records into {db_file}!")


if __name__ == '__main__':
    parse_all_tournaments()
