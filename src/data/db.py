import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'tta_ratings.db'

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    country_code TEXT,
    title TEXT,
    title_count INTEGER DEFAULT 0,
    badge_reason TEXT,
    last_played TEXT,
    peak_title TEXT,
    peak_year INTEGER
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_players_nocase ON players(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament TEXT,
    date TEXT NOT NULL,
    player_count INTEGER NOT NULL,
    player1 TEXT NOT NULL,
    score1 REAL NOT NULL,
    player2 TEXT NOT NULL,
    score2 REAL NOT NULL,
    player3 TEXT,
    score3 REAL,
    player4 TEXT,
    score4 REAL,
    replay_code TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament);
CREATE INDEX IF NOT EXISTS idx_matches_p1 ON matches(player1, date);
CREATE INDEX IF NOT EXISTS idx_matches_p2 ON matches(player2, date);
CREATE INDEX IF NOT EXISTS idx_matches_p3 ON matches(player3, date);
CREATE INDEX IF NOT EXISTS idx_matches_p4 ON matches(player4, date);

CREATE TABLE IF NOT EXISTS pairwise_matches (
    pairwise_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    tournament TEXT,
    player_count INTEGER NOT NULL,
    player_a TEXT NOT NULL,
    player_b TEXT NOT NULL,
    score_a REAL NOT NULL,
    score_b REAL NOT NULL,
    outcome_a REAL NOT NULL,
    weight REAL NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pw_date ON pairwise_matches(date);
CREATE INDEX IF NOT EXISTS idx_pw_player_a ON pairwise_matches(player_a);
CREATE INDEX IF NOT EXISTS idx_pw_player_b ON pairwise_matches(player_b);
CREATE INDEX IF NOT EXISTS idx_pw_match_id ON pairwise_matches(match_id);

CREATE TABLE IF NOT EXISTS player_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type TEXT NOT NULL,
    player_count INTEGER DEFAULT 0,
    player_name TEXT NOT NULL,
    rating REAL NOT NULL,
    rd REAL NOT NULL,
    sigma REAL NOT NULL,
    c_rating REAL NOT NULL,
    rank INTEGER,
    rank_delta INTEGER DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    opponents_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    last_played TEXT,
    UNIQUE(model_type, player_count, player_name)
);

CREATE INDEX IF NOT EXISTS idx_pr_model_fmt_rank ON player_ratings(model_type, player_count, rank);
CREATE INDEX IF NOT EXISTS idx_pr_model_fmt_player ON player_ratings(model_type, player_count, player_name);

CREATE TABLE IF NOT EXISTS rating_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type TEXT NOT NULL,
    player_count INTEGER DEFAULT 0,
    player_name TEXT NOT NULL,
    period_date TEXT NOT NULL,
    rating REAL NOT NULL,
    rd REAL NOT NULL,
    c_rating REAL NOT NULL
);

-- Covering index for high-performance player history queries
CREATE INDEX IF NOT EXISTS idx_rh_player_fast ON rating_history(player_name, player_count, period_date, rating);

CREATE TABLE IF NOT EXISTS official_baseline (
    player_name TEXT PRIMARY KEY,
    rank INTEGER,
    rank_delta REAL,
    c_rating REAL,
    c_rating_delta REAL,
    rating REAL,
    rating_delta REAL,
    rd REAL,
    rd_delta REAL,
    opps INTEGER,
    opps_delta REAL,
    win_rate REAL,
    win_rate_delta REAL,
    last_played TEXT
);

CREATE TABLE IF NOT EXISTS yearly_player_stats (
    year INTEGER NOT NULL,
    player_count INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    opponents_count INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0.0,
    last_played TEXT,
    career_opps INTEGER NOT NULL DEFAULT 0,
    career_wins INTEGER NOT NULL DEFAULT 0,
    career_losses INTEGER NOT NULL DEFAULT 0,
    career_draws INTEGER NOT NULL DEFAULT 0,
    career_win_rate REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (year, player_count, player_name)
);

CREATE TABLE IF NOT EXISTS pipeline_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cutoff_date TEXT,
    matches_added INTEGER DEFAULT 0,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_pu_date ON pipeline_updates(updated_at);
CREATE INDEX IF NOT EXISTS idx_yps_lookup ON yearly_player_stats(year, player_count, player_name);
CREATE INDEX IF NOT EXISTS idx_rh_date ON rating_history(model_type, player_count, period_date);

CREATE TABLE IF NOT EXISTS walk_forward_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type TEXT NOT NULL,
    player_count INTEGER DEFAULT 0,
    period_month TEXT NOT NULL,
    matches_evaluated INTEGER NOT NULL,
    brier_score REAL NOT NULL,
    ece REAL NOT NULL,
    log_loss REAL,
    accuracy REAL,
    bin_data_json TEXT,
    UNIQUE(model_type, player_count, period_month)
);

CREATE INDEX IF NOT EXISTS idx_wfc_lookup ON walk_forward_calibration(model_type, player_count, period_month);
CREATE INDEX IF NOT EXISTS idx_wfc_pc_month ON walk_forward_calibration(player_count, period_month);

CREATE TABLE IF NOT EXISTS standard_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type TEXT NOT NULL,
    player_count INTEGER DEFAULT 0,
    period_month TEXT NOT NULL DEFAULT 'AGGREGATED',
    matches_evaluated INTEGER NOT NULL,
    brier_score REAL NOT NULL,
    ece REAL NOT NULL,
    log_loss REAL,
    accuracy REAL,
    bin_data_json TEXT,
    UNIQUE(model_type, player_count, period_month)
);

CREATE INDEX IF NOT EXISTS idx_std_calib_lookup ON standard_calibration(model_type, player_count, period_month);
CREATE INDEX IF NOT EXISTS idx_std_calib_pc_month ON standard_calibration(player_count, period_month);

CREATE TABLE IF NOT EXISTS delta_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_snapshot_file TEXT,
    cutoff_date TEXT,
    description TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS webmaster_notes (
    key TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS faq_sections (
    key TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS cms_content_blocks (
    page_id TEXT NOT NULL,
    block_key TEXT NOT NULL,
    title TEXT,
    content_html TEXT,
    content_markdown TEXT,
    is_deleted INTEGER DEFAULT 0,
    relative_to TEXT,
    placement TEXT,
    sort_order INTEGER DEFAULT 0,
    is_custom_card INTEGER DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (page_id, block_key)
);

CREATE TABLE IF NOT EXISTS player_achievements (
    player_name TEXT PRIMARY KEY,
    total_titles INTEGER DEFAULT 0,
    world_titles INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS tournament_records (
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
CREATE INDEX IF NOT EXISTS idx_tr_player ON tournament_records(player_name);
CREATE INDEX IF NOT EXISTS idx_tr_tourney ON tournament_records(tournament_name);
"""

_SCHEMA_MIGRATED = False

def ensure_schema_migrations(conn=None):
    """Ensures newly introduced columns exist in existing tables across deployments."""
    global _SCHEMA_MIGRATED
    if _SCHEMA_MIGRATED:
        return
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    try:
        # Check players table columns
        p_cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
        if 'badge_reason' not in p_cols:
            try:
                conn.execute("ALTER TABLE players ADD COLUMN badge_reason TEXT")
            except sqlite3.OperationalError:
                pass
        if 'peak_title' not in p_cols:
            try:
                conn.execute("ALTER TABLE players ADD COLUMN peak_title TEXT")
            except sqlite3.OperationalError:
                pass
        if 'peak_year' not in p_cols:
            try:
                conn.execute("ALTER TABLE players ADD COLUMN peak_year INTEGER")
            except sqlite3.OperationalError:
                pass

        # Matches & pairwise migrations
        m_cols = {row[1] for row in conn.execute("PRAGMA table_info(matches)").fetchall()}
        if 'glicko_eligible' not in m_cols:
            try:
                conn.execute("ALTER TABLE matches ADD COLUMN glicko_eligible INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass
        if 'replay_code' not in m_cols:
            try:
                conn.execute("ALTER TABLE matches ADD COLUMN replay_code TEXT")
            except sqlite3.OperationalError:
                pass

        pw_cols = {row[1] for row in conn.execute("PRAGMA table_info(pairwise_matches)").fetchall()}
        if 'glicko_eligible' not in pw_cols:
            try:
                conn.execute("ALTER TABLE pairwise_matches ADD COLUMN glicko_eligible INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass

        # Yearly player stats career columns
        y_cols = {row[1] for row in conn.execute("PRAGMA table_info(yearly_player_stats)").fetchall()}
        for col, col_def in [
            ('career_opps', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_wins', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_losses', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_draws', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_win_rate', 'REAL NOT NULL DEFAULT 0.0')
        ]:
            if col not in y_cols:
                try:
                    conn.execute(f"ALTER TABLE yearly_player_stats ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass

        # CMS content blocks columns
        cms_cols = {row[1] for row in conn.execute("PRAGMA table_info(cms_content_blocks)").fetchall()}
        for col, col_def in [
            ('is_deleted', 'INTEGER DEFAULT 0'),
            ('relative_to', 'TEXT'),
            ('placement', 'TEXT'),
            ('sort_order', 'INTEGER DEFAULT 0'),
            ('is_custom_card', 'INTEGER DEFAULT 0')
        ]:
            if col not in cms_cols:
                try:
                    conn.execute(f"ALTER TABLE cms_content_blocks ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass

        # Tournament records columns
        tr_cols = {row[1] for row in conn.execute("PRAGMA table_info(tournament_records)").fetchall()}
        for col, col_def in [
            ('medal', 'TEXT'),
            ('details', 'TEXT'),
            ('is_career_total', 'INTEGER DEFAULT 0')
        ]:
            if col not in tr_cols:
                try:
                    conn.execute(f"ALTER TABLE tournament_records ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass

        conn.commit()
        _SCHEMA_MIGRATED = True

        # Deduplicate Royal League quarterly tournament records
        cleanup_duplicate_tournament_records(conn)

        # Check if peak_title needs population (if columns were just added or empty)
        try:
            count_row = conn.execute("SELECT COUNT(*) FROM players WHERE peak_title IS NOT NULL").fetchone()
            if count_row and count_row[0] == 0:
                from src.data.badges import derive_tournament_badges
                derive_tournament_badges()
        except Exception:
            pass

        # Sync tournament achievements with canonical player names
        try:
            from src.data.hall_of_fame import sync_tournament_achievements
            sync_tournament_achievements(conn)
        except Exception:
            pass

    except Exception:
        pass
    finally:
        if close_after:
            conn.close()


def cleanup_duplicate_tournament_records(conn):
    """
    Cleans up duplicate tournament records, standardizes quarters to canonical seasons,
    normalizes shorthand tournament names (ML, NL, DC, PL), consolidates multi-stage events
    (Survivors Cup, Leaderboard Trophy) into unified single-row entries, and restricts
    medals strictly to top-tier division podiums.
    """
    import re
    rl_season_map = {
        '2024 Q3': 'Season 1',
        '2024 Q4': 'Season 2',
        '2025 Q1': 'Season 3',
        '2025 Q2': 'Season 4',
        '2025 Q3': 'Season 5',
        '2025 Q4': 'Season 6',
        '2026 Q1': 'Season 7',
        '2026 Q2': 'Season 8',
        '2026 Q3': 'Season 9',
    }

    try:
        has_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tournament_records'").fetchone()
        if not has_table:
            return

        # 1. Merge Royal League quarterly records into match rows
        q_rows = conn.execute(
            "SELECT record_id, player_name, season, division, placement, points, medal, details, finish_date "
            "FROM tournament_records WHERE tournament_name = 'Royal League' AND season LIKE '%Q%'"
        ).fetchall()

        for r in q_rows:
            rec_id = r[0]
            pname = r[1]
            quarter = r[2]
            r_medal = r[6]
            r_details = r[7]
            r_fdate = r[8]

            s_target = rl_season_map.get(quarter)
            if not s_target:
                continue

            match_row = conn.execute(
                "SELECT record_id, medal, details, finish_date FROM tournament_records "
                "WHERE tournament_name = 'Royal League' AND season = ? AND LOWER(player_name) = LOWER(?)",
                (s_target, pname)
            ).fetchone()

            if match_row:
                m_id = match_row[0]
                m_medal = match_row[1]
                m_details = match_row[2] or ''
                m_fdate = match_row[3]

                medal = r_medal or m_medal
                q_det = r_details or ''
                if q_det and q_det not in m_details:
                    merged_details = f"{q_det} • {m_details}" if m_details else q_det
                else:
                    merged_details = m_details or q_det

                f_date = m_fdate or r_fdate

                conn.execute(
                    "UPDATE tournament_records SET medal = ?, details = ?, finish_date = ? WHERE record_id = ?",
                    (medal, merged_details, f_date, m_id)
                )
                conn.execute("DELETE FROM tournament_records WHERE record_id = ?", (rec_id,))
            else:
                conn.execute(
                    "UPDATE tournament_records SET season = ? WHERE record_id = ?",
                    (s_target, rec_id)
                )

        # Standardize any remaining quarterly season references
        for q_name, s_name in rl_season_map.items():
            conn.execute("UPDATE tournament_records SET season = ? WHERE tournament_name = 'Royal League' AND season = ?", (s_name, q_name))

        # 2. Standardize Shorthand Tournaments (ML_*, NL_*, DC_*, PL_*, Slow Burn)
        sh_rows = conn.execute("SELECT record_id, tournament_name, season FROM tournament_records").fetchall()
        updates = []
        for r in sh_rows:
            rec_id, t, s = r[0], r[1], r[2]
            new_t, new_s = None, None

            # Mercurial Ladder
            m_ml = re.match(r'ML_[sr]0?(\d+)', t, re.IGNORECASE)
            if m_ml:
                new_t = 'Mercurial Ladder'
                new_s = f"Season {int(m_ml.group(1))}"

            # Sodium Ladder
            m_nl = re.match(r'NL_s0?(\d+)', t, re.IGNORECASE)
            if m_nl:
                new_t = 'Sodium Ladder'
                new_s = f"Season {int(m_nl.group(1))}"
            elif re.match(r'Sodium Ladder Season\s*0?(\d+)', t, re.IGNORECASE):
                m_sod = re.match(r'Sodium Ladder Season\s*0?(\d+)', t, re.IGNORECASE)
                new_t = 'Sodium Ladder'
                new_s = f"Season {int(m_sod.group(1))}"

            # Premier League
            m_pl = re.match(r'(?:PL_s|Premier League\s+)0?(\d+)', t, re.IGNORECASE)
            if m_pl:
                new_t = 'Premier League'
                new_s = f"Season {int(m_pl.group(1))}"

            # Diamond Cup
            m_dc = re.match(r'DC_s0?(\d+)', t, re.IGNORECASE)
            if m_dc:
                new_t = 'Diamond Cup'
                new_s = f"Season {int(m_dc.group(1))}"

            # Slow Burn
            m_sb = re.match(r'Slow Burn\s*S?0?(\d+)', t, re.IGNORECASE)
            if m_sb:
                new_t = 'Slow Burn'
                new_s = f"Season {int(m_sb.group(1))}"

            if new_t:
                updates.append((new_t, new_s or s, rec_id))

        if updates:
            conn.executemany("UPDATE tournament_records SET tournament_name = ?, season = ? WHERE record_id = ?", updates)

        # 3. Multi-Stage Consolidation for Survivors Cup 2026
        sc_rows = conn.execute(
            "SELECT record_id, player_name, tournament_name, division, placement, points, details, finish_date "
            "FROM tournament_records WHERE tournament_name LIKE 'Survivors Cup 2026%'"
        ).fetchall()
        if sc_rows:
            sc_players = {}
            for r in sc_rows:
                p = r[1]
                if p not in sc_players:
                    sc_players[p] = []
                sc_players[p].append(r)

            total_field = len(sc_players)
            player_ranks = []
            for p, p_rows in sc_players.items():
                max_st = 1
                tot_g, tot_w, tot_pts = 0, 0, 0
                latest_date = '2026-01-01'
                exit_placement = 3

                for r in p_rows:
                    t_str = r[2]
                    m_st = re.search(r'Stage\s*(\d+)', t_str, re.IGNORECASE)
                    st_num = int(m_st.group(1)) if m_st else 1
                    if st_num >= max_st:
                        max_st = st_num
                        m_pl = re.match(r'(\d+)\s*/', r[4] or '')
                        if m_pl:
                            exit_placement = int(m_pl.group(1))
                        f_d = r[7]
                        if f_d and f_d > latest_date:
                            latest_date = f_d

                    det = r[6] or ''
                    m_match = re.search(r'(\d+)\s+matches played,\s+(\d+)\s+victories', det)
                    if m_match:
                        tot_g += int(m_match.group(1))
                        tot_w += int(m_match.group(2))
                    else:
                        tot_g += 1

                    pts_str = r[5] or ''
                    m_pts = re.search(r'(\d+)\s*pts', pts_str)
                    if m_pts:
                        tot_pts += int(m_pts.group(1))

                wr = round(tot_w / tot_g * 100, 1) if tot_g > 0 else 0.0
                player_ranks.append({
                    'player_name': p,
                    'max_stage': max_st,
                    'exit_placement': exit_placement,
                    'total_points': tot_pts,
                    'total_games': tot_g,
                    'total_wins': tot_w,
                    'win_rate': wr,
                    'finish_date': latest_date
                })

            player_ranks.sort(key=lambda x: (-x['max_stage'], x['exit_placement'], -x['total_points']))
            all_sc_ids = [r[0] for r in sc_rows]
            conn.execute(f"DELETE FROM tournament_records WHERE record_id IN ({','.join('?' for _ in all_sc_ids)})", all_sc_ids)

            new_sc_records = []
            for rank_idx, pr in enumerate(player_ranks, 1):
                medal = 'gold' if rank_idx == 1 else ('silver' if rank_idx == 2 else ('bronze' if rank_idx == 3 else ''))
                det = f"Advanced to Stage {pr['max_stage']} • {pr['total_games']} matches played, {pr['total_wins']} victories ({pr['win_rate']}% win rate) • Cumulative Score: {pr['total_points']:,} pts"
                new_sc_records.append((
                    pr['player_name'],
                    'Survivors Cup',
                    '2026',
                    'Championship',
                    f"{rank_idx} / {total_field}",
                    f"{pr['total_points']} pts",
                    medal,
                    det,
                    pr['finish_date'],
                    0
                ))

            conn.executemany("""
                INSERT INTO tournament_records (player_name, tournament_name, season, division, placement, points, medal, details, finish_date, is_career_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, new_sc_records)

        # 4. Multi-Stage Consolidation for Leaderboard Trophy 2025
        lt_rows = conn.execute(
            "SELECT record_id, player_name, tournament_name, division, placement, points, details, finish_date "
            "FROM tournament_records WHERE tournament_name LIKE 'Leaderboard Trophy 2025%'"
        ).fetchall()
        if lt_rows:
            lt_players = {}
            for r in lt_rows:
                p = r[1]
                if p not in lt_players:
                    lt_players[p] = []
                lt_players[p].append(r)

            total_field = len(lt_players)
            player_ranks = []
            for p, p_rows in lt_players.items():
                max_st = 1
                tot_g, tot_w = 0, 0
                latest_date = '2026-01-01'
                exit_placement = 3

                for r in p_rows:
                    t_str = r[2]
                    m_st = re.search(r'Stage\s*(\d+)', t_str, re.IGNORECASE)
                    st_num = int(m_st.group(1)) if m_st else 1
                    if st_num >= max_st:
                        max_st = st_num
                        m_pl = re.match(r'(\d+)\s*/', r[4] or '')
                        if m_pl:
                            exit_placement = int(m_pl.group(1))
                        f_d = r[7]
                        if f_d and f_d > latest_date:
                            latest_date = f_d

                    det = r[6] or ''
                    m_match = re.search(r'(\d+)\s+matches played,\s+(\d+)\s+victories', det)
                    if m_match:
                        tot_g += int(m_match.group(1))
                        tot_w += int(m_match.group(2))
                    else:
                        tot_g += 1

                wr = round(tot_w / tot_g * 100, 1) if tot_g > 0 else 0.0
                player_ranks.append({
                    'player_name': p,
                    'max_stage': max_st,
                    'exit_placement': exit_placement,
                    'total_games': tot_g,
                    'total_wins': tot_w,
                    'win_rate': wr,
                    'finish_date': latest_date
                })

            player_ranks.sort(key=lambda x: (-x['max_stage'], x['exit_placement']))
            all_lt_ids = [r[0] for r in lt_rows]
            conn.execute(f"DELETE FROM tournament_records WHERE record_id IN ({','.join('?' for _ in all_lt_ids)})", all_lt_ids)

            new_lt_records = []
            for rank_idx, pr in enumerate(player_ranks, 1):
                medal = 'gold' if rank_idx == 1 else ('silver' if rank_idx == 2 else ('bronze' if rank_idx == 3 else ''))
                det = f"Advanced to Stage {pr['max_stage']} • {pr['total_games']} matches played, {pr['total_wins']} victories ({pr['win_rate']}% win rate)"
                new_lt_records.append((
                    pr['player_name'],
                    'Leaderboard Trophy',
                    '2025',
                    'Championship',
                    f"{rank_idx} / {total_field}",
                    '',
                    medal,
                    det,
                    pr['finish_date'],
                    0
                ))

            conn.executemany("""
                INSERT INTO tournament_records (player_name, tournament_name, season, division, placement, points, medal, details, finish_date, is_career_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, new_lt_records)

        # 5. Clear lower-tier medals (Only award medals for top tier of each format)
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name = 'Royal League' AND LOWER(division) != 'emperor'")
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name IN ('International Championship', 'Intermezzo Championship') AND LOWER(division) NOT IN ('grandmaster', 'championship', 'premier')")
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name = 'Mercurial Ladder' AND LOWER(division) NOT IN ('tier 1', 'tier 01', 'hydrogen', 'mercurial tier', 'premium tier 1') AND LOWER(division) NOT LIKE '1-hydrogen%'")
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name = 'Sodium Ladder' AND LOWER(division) NOT IN ('tier 1', 'tier 01', '01 tier', '1 tier', 'sodium tier')")
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name LIKE 'TCL Round%'")
        conn.execute("UPDATE tournament_records SET medal = '' WHERE tournament_name IN ('Premier League', 'Diamond Cup', 'Slow Burn') AND LOWER(division) NOT IN ('tier 1', 'division 1', 'championship', 'premier', 'main')")

        conn.commit()
    except Exception:
        pass


def get_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.execute('PRAGMA busy_timeout = 60000;')
    # Do NOT force WAL mode on PythonAnywhere / NFS filesystems
    is_pa = bool(os.environ.get('PYTHONANYWHERE_DOMAIN') or os.environ.get('PYTHONANYWHERE_SITE'))
    if is_pa:
        conn.execute('PRAGMA journal_mode = DELETE;')

    global _SCHEMA_MIGRATED
    if not _SCHEMA_MIGRATED:
        ensure_schema_migrations(conn)

    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    with conn:
        conn.executescript(SCHEMA_SQL)
        # Migrate glicko_eligible if not yet present
        try:
            conn.execute("ALTER TABLE matches ADD COLUMN glicko_eligible INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE matches ADD COLUMN replay_code TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE pairwise_matches ADD COLUMN glicko_eligible INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE players ADD COLUMN badge_reason TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE players ADD COLUMN peak_title TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE players ADD COLUMN peak_year INTEGER")
        except sqlite3.OperationalError:
            pass
        for col, col_def in [
            ('career_opps', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_wins', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_losses', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_draws', 'INTEGER NOT NULL DEFAULT 0'),
            ('career_win_rate', 'REAL NOT NULL DEFAULT 0.0')
        ]:
            try:
                conn.execute(f"ALTER TABLE yearly_player_stats ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass

        # Migrate cms_content_blocks columns
        for col, col_def in [
            ('is_deleted', 'INTEGER DEFAULT 0'),
            ('relative_to', 'TEXT'),
            ('placement', 'TEXT'),
            ('sort_order', 'INTEGER DEFAULT 0'),
            ('is_custom_card', 'INTEGER DEFAULT 0')
        ]:
            try:
                conn.execute(f"ALTER TABLE cms_content_blocks ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass

        # Migrate existing faq_sections into cms_content_blocks
        try:
            conn.execute("""
                INSERT OR IGNORE INTO cms_content_blocks (page_id, block_key, title, content_html, content_markdown, updated_at)
                SELECT 'faq', key, title, content, content, updated_at FROM faq_sections
            """)
        except sqlite3.OperationalError:
            pass
    conn.close()

def get_all_cms_blocks(conn=None):
    """Returns a dictionary of all custom CMS blocks keyed by (page_id, block_key)."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        cur = conn.execute("""
            SELECT page_id, block_key, title, content_html, content_markdown,
                   is_deleted, relative_to, placement, sort_order, is_custom_card, updated_at
            FROM cms_content_blocks
        """)
        rows = cur.fetchall()
        return {(r['page_id'], r['block_key']): dict(r) for r in rows}
    finally:
        if close_after:
            conn.close()

def save_cms_block(page_id: str, block_key: str, title: str, content_html: str, content_markdown: str,
                   relative_to: str = None, placement: str = None, sort_order: int = 0,
                   is_custom_card: int = 0, is_deleted: int = 0, conn=None):
    """Persists an updated CMS block to the database."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        with conn:
            conn.execute("""
                INSERT INTO cms_content_blocks (
                    page_id, block_key, title, content_html, content_markdown,
                    is_deleted, relative_to, placement, sort_order, is_custom_card, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(page_id, block_key) DO UPDATE SET
                    title = excluded.title,
                    content_html = excluded.content_html,
                    content_markdown = excluded.content_markdown,
                    is_deleted = excluded.is_deleted,
                    relative_to = COALESCE(excluded.relative_to, cms_content_blocks.relative_to),
                    placement = COALESCE(excluded.placement, cms_content_blocks.placement),
                    sort_order = excluded.sort_order,
                    is_custom_card = excluded.is_custom_card,
                    updated_at = CURRENT_TIMESTAMP
            """, (page_id, block_key, title, content_html, content_markdown,
                  is_deleted, relative_to, placement, sort_order, is_custom_card))
    finally:
        if close_after:
            conn.close()

def delete_cms_block(page_id: str, block_key: str, conn=None):
    """Marks a card as deleted (is_deleted = 1). If it's a default template card, creates an entry with is_deleted = 1."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        with conn:
            cur = conn.execute("SELECT is_custom_card FROM cms_content_blocks WHERE page_id = ? AND block_key = ?", (page_id, block_key))
            row = cur.fetchone()
            if row:
                conn.execute("UPDATE cms_content_blocks SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE page_id = ? AND block_key = ?", (page_id, block_key))
            else:
                conn.execute("""
                    INSERT INTO cms_content_blocks (page_id, block_key, title, content_html, content_markdown, is_deleted, is_custom_card, updated_at)
                    VALUES (?, ?, '', '', '', 1, 0, CURRENT_TIMESTAMP)
                """, (page_id, block_key))
            return True
    finally:
        if close_after:
            conn.close()

def restore_cms_block(page_id: str, block_key: str, conn=None):
    """Restores a deleted block (either unsets is_deleted for custom card, or deletes override for default card)."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        with conn:
            cur = conn.execute("SELECT is_custom_card FROM cms_content_blocks WHERE page_id = ? AND block_key = ?", (page_id, block_key))
            row = cur.fetchone()
            if row:
                if row['is_custom_card'] == 1:
                    conn.execute("UPDATE cms_content_blocks SET is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE page_id = ? AND block_key = ?", (page_id, block_key))
                else:
                    conn.execute("DELETE FROM cms_content_blocks WHERE page_id = ? AND block_key = ?", (page_id, block_key))
                return True
            return False
    finally:
        if close_after:
            conn.close()

def revert_cms_block(page_id: str, block_key: str, conn=None):
    """Deletes an override from cms_content_blocks, reverting the block to template default."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        with conn:
            cur = conn.execute("DELETE FROM cms_content_blocks WHERE page_id = ? AND block_key = ?", (page_id, block_key))
            return cur.rowcount > 0
    finally:
        if close_after:
            conn.close()

def revert_all_cms_blocks(page_id: str = None, conn=None):
    """Deletes all overrides (optionally filtered by page_id), reverting blocks to template defaults."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        with conn:
            if page_id:
                cur = conn.execute("DELETE FROM cms_content_blocks WHERE page_id = ?", (page_id,))
            else:
                cur = conn.execute("DELETE FROM cms_content_blocks")
            return cur.rowcount
    finally:
        if close_after:
            conn.close()

def get_cms_block(page_id: str, block_key: str, conn=None):
    """Fetches a single CMS block by page_id and block_key."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        cur = conn.execute("""
            SELECT page_id, block_key, title, content_html, content_markdown,
                   is_deleted, relative_to, placement, sort_order, is_custom_card, updated_at
            FROM cms_content_blocks
            WHERE page_id = ? AND block_key = ?
        """, (page_id, block_key))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if close_after:
            conn.close()

def get_custom_cards(page_id: str = None, conn=None):
    """Returns all active (non-deleted) custom-created cards, optionally filtered by page_id."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    try:
        if page_id:
            cur = conn.execute("""
                SELECT page_id, block_key, title, content_html, content_markdown,
                       relative_to, placement, sort_order, updated_at
                FROM cms_content_blocks
                WHERE page_id = ? AND is_custom_card = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
                ORDER BY sort_order ASC, updated_at ASC
            """, (page_id,))
        else:
            cur = conn.execute("""
                SELECT page_id, block_key, title, content_html, content_markdown,
                       relative_to, placement, sort_order, updated_at
                FROM cms_content_blocks
                WHERE is_custom_card = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
                ORDER BY sort_order ASC, updated_at ASC
            """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        if close_after:
            conn.close()

def log_pipeline_update(conn, cutoff_date=None, matches_added=0, description=""):
    """Logs a webmaster update event for delta tracking."""
    with conn:
        conn.execute(
            "INSERT INTO pipeline_updates (cutoff_date, matches_added, description) VALUES (?, ?, ?)",
            (cutoff_date, matches_added, description)
        )

def populate_yearly_stats(conn):
    """Populates yearly_player_stats by aggregating pairwise matches per year and player format with full player_a / player_b symmetry and career-to-date cumulative stats."""
    with conn:
        conn.execute("DELETE FROM yearly_player_stats")
        # 1. Format-specific yearly stats (player_count 2, 3, 4)
        conn.execute("""
            WITH pp AS (
                SELECT 
                    CAST(SUBSTR(date, 1, 4) AS INTEGER) as yr,
                    player_count,
                    player_a as player_name,
                    CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END as win,
                    CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END as loss,
                    CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END as draw,
                    date
                FROM pairwise_matches
                UNION ALL
                SELECT 
                    CAST(SUBSTR(date, 1, 4) AS INTEGER) as yr,
                    player_count,
                    player_b as player_name,
                    CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END as win,
                    CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END as loss,
                    CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END as draw,
                    date
                FROM pairwise_matches
            ),
            season_agg AS (
                SELECT 
                    yr,
                    player_count,
                    player_name,
                    COUNT(*) as opps,
                    SUM(win) as wins,
                    SUM(loss) as losses,
                    SUM(draw) as draws,
                    ROUND((SUM(win) + 0.5 * SUM(draw)) / COUNT(*) * 100.0, 1) as win_rate,
                    MAX(date) as last_played
                FROM pp
                GROUP BY yr, player_count, player_name
            )
            INSERT INTO yearly_player_stats (
                year, player_count, player_name, opponents_count, wins, losses, draws, win_rate, last_played,
                career_opps, career_wins, career_losses, career_draws, career_win_rate
            )
            SELECT 
                yr, player_count, player_name, opps, wins, losses, draws, win_rate, last_played,
                SUM(opps) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_opps,
                SUM(wins) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_wins,
                SUM(losses) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_losses,
                SUM(draws) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_draws,
                ROUND(
                    (SUM(wins) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                     + 0.5 * SUM(draws) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW))
                    / SUM(opps) OVER (PARTITION BY player_count, player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) * 100.0,
                    1
                ) as c_win_rate
            FROM season_agg
        """)

        # 2. All-Formats yearly stats (player_count = 0)
        conn.execute("""
            WITH pp AS (
                SELECT 
                    CAST(SUBSTR(date, 1, 4) AS INTEGER) as yr,
                    player_a as player_name,
                    CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END as win,
                    CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END as loss,
                    CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END as draw,
                    date
                FROM pairwise_matches
                UNION ALL
                SELECT 
                    CAST(SUBSTR(date, 1, 4) AS INTEGER) as yr,
                    player_b as player_name,
                    CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END as win,
                    CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END as loss,
                    CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END as draw,
                    date
                FROM pairwise_matches
            ),
            season_agg AS (
                SELECT 
                    yr,
                    0 as player_count,
                    player_name,
                    COUNT(*) as opps,
                    SUM(win) as wins,
                    SUM(loss) as losses,
                    SUM(draw) as draws,
                    ROUND((SUM(win) + 0.5 * SUM(draw)) / COUNT(*) * 100.0, 1) as win_rate,
                    MAX(date) as last_played
                FROM pp
                GROUP BY yr, player_name
            )
            INSERT INTO yearly_player_stats (
                year, player_count, player_name, opponents_count, wins, losses, draws, win_rate, last_played,
                career_opps, career_wins, career_losses, career_draws, career_win_rate
            )
            SELECT 
                yr, player_count, player_name, opps, wins, losses, draws, win_rate, last_played,
                SUM(opps) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_opps,
                SUM(wins) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_wins,
                SUM(losses) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_losses,
                SUM(draws) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as c_draws,
                ROUND(
                    (SUM(wins) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                     + 0.5 * SUM(draws) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW))
                    / SUM(opps) OVER (PARTITION BY player_name ORDER BY yr ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) * 100.0,
                    1
                ) as c_win_rate
            FROM season_agg
        """)

def ensure_yearly_stats(conn):
    """Ensures yearly_player_stats table exists and contains data."""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='yearly_player_stats'")
    if not c.fetchone():
        init_db()
    c.execute("SELECT COUNT(*) FROM yearly_player_stats")
    row = c.fetchone()
    if not row or row[0] == 0:
        populate_yearly_stats(conn)

