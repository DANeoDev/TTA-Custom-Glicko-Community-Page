"""Database connectivity and schema initialization for TTA-Glicko2-WHR."""
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
    last_played TEXT
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);

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
    score4 REAL
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament);

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

CREATE INDEX IF NOT EXISTS idx_rh_player ON rating_history(model_type, player_count, player_name, period_date);

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
"""

def get_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.execute('PRAGMA journal_mode = WAL;')
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
            conn.execute("ALTER TABLE pairwise_matches ADD COLUMN glicko_eligible INTEGER NOT NULL DEFAULT 1")
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

