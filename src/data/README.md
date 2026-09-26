# Data Pipeline & Database Infrastructure (`src/data`)

This directory houses the data ingestion, validation, database management, and tournament badge derivation pipelines for the **Through the Ages (TTA) Rating Portal**.

---

## 1. Overview

The platform uses an embedded SQLite database located at `data/tta_ratings.db`. The modules in `src/data` are responsible for:
- Connecting to SQLite with proper concurrency settings and row factory bindings (`db.py`).
- Loading and normalizing raw game logs across online platforms and competitive spreadsheets (`loader.py`, `merger.py`).
- Enforcing schema consistency and completeness across historical matches (`completeness.py`, `consistency.py`).
- Parsing tournament placings, medals, and seasons (`parse_tournaments.py`, `hall_of_fame.py`).
- Deriving official competitive titles, recency badges, and career peak records (`badges.py`).

---

## 2. Database Schema

The core relational database `data/tta_ratings.db` contains the following primary tables:

| Table | Description |
|---|---|
| `matches` | Individual multi-player matches (game ID, date, format, player placements, scores, tournament identifier). |
| `pairwise_matches` | Normalized head-to-head pairs generated from multiplayer encounters for Bayesian validation. |
| `players` | Registered players, active competitive title (`title`), peak title (`peak_title`), peak year (`peak_year`), nationality, and recency timestamps. |
| `player_ratings` | Latest computed ratings across all 5 engines (`glicko2_daneo`, `glicko2_std`, `glicko2_mp`, `glicko2_adapt`, `whr`) and formats (Duel, 3P, 4P, All). |
| `rating_history` | Time-series progression records ($R$, $\mathrm{RD}$, $C$) per player, model, and season reset mode. |
| `tournament_records` | Granular tournament results: season, division, placement, medal (Gold, Silver, Bronze), finish date, and hall of fame standings. |
| `yearly_player_stats` | Annual career breakdowns: matches played, wins, losses, draws, win rate, and peak rating. |
| `player_achievements` | Hall of fame highlights, major tournament victories, and title defenses. |

---

## 3. Module Breakdown

### `badges.py` &mdash; Official Badge & Title Derivation Engine
Implements the official tournament hierarchy and recency rules:
- **1-Year Recency Rule**: Active tournament tier badges are displayed only if a player has competed in an accredited tournament division within the last 12 months (365 days).
- **Super GM (`SGM`)**: The highest non-WC rank. Conferred upon players who have won the premier division of the International Championship, Intermezzo Championship, or Royal League within the last 12 months.
- **World Champion (`WC`)**: Held exclusively by the Reigning World Champion (currently `a440`).
- **Hierarchy Order**:
  1. `WC` (World Champion, Order 0)
  2. `SGM` (Super GM, Order 1)
  3. `GM` (Grandmaster, Order 2)
  4. `M` (Master, Order 3)
  5. `P` (Platinum, Order 4)
  6. `G` (Gold, Order 5)
  7. `S` (Silver, Order 6)
  8. `B` (Bronze, Order 7)
  9. `W` (Wood, Order 8)
- **Career Peak Tracking**: Computes all-time peak titles and years, preserving historical distinctions even when an active badge expires.

### `db.py` &mdash; Database Lifecycle & Initialization
Provides `get_connection(db_path)` with context management, foreign key activation, and automatic column schema migrations (`peak_title`, `peak_year`).

### `loader.py` & `merger.py` &mdash; Match Ingestion & Deduplication
- Parses raw match reports from CSV files, JSON payloads, and Google Sheets exports.
- Resolves alias discrepancies (e.g. casing variations, special characters) into canonical player identifiers.
- Deduplicates parallel match submissions from multiple tournament directors.

### `completeness.py` & `consistency.py` &mdash; Verification & Auditing
- Scans `matches` for missing player references, impossible game dates, and invalid player counts.
- Cross-references tournament standings with logged match results to ensure zero data discrepancies.

### `parse_tournaments.py` & `hall_of_fame.py` &mdash; Tournament Records
- Scrapes and parses official finish tables from competitive Through the Ages communities:
  - International Championship (4-Player, Seasons 1&ndash;34)
  - Intermezzo Championship (3-Player, Seasons 1&ndash;31)
  - Royal League (2-Player Duel, Seasons 1&ndash;9)
  - World Championship (2023, 2024, 2025)

---

## 4. Usage

To derive and refresh all tournament titles and peak records in the database:

```bash
python -m src.data.badges
```

To run consistency audits across all matches and tournament entries:

```bash
python -m src.data.consistency
```
