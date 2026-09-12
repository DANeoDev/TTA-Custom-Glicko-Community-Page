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
    conn.close()
