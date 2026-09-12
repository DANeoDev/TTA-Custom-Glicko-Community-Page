# System Architecture & Technical Specifications

This document outlines the software design, database schemas, and data flow of the **TTA-Glicko2-WHR** platform.

---

## 1. High-Level Data Flow

```
[Raw CSVs]
  ├── all_matches.csv (131,424 matches)
  └── ratings_overall.csv (3,489 players)
         │
         ▼
[Data Ingestion (src/data/loader.py)]
  • Parses tournament metadata & scores
  • Expands 2p/3p/4p matches into 376,425 pairwise encounters
  • Assigns fractional weights w = 1 / (N - 1)
         │
         ▼
[SQLite Storage (data/tta_ratings.db)]
  • matches, pairwise_matches, players
         │
         ▼
[Rating Calculators (src/models/)]
  ├── Glicko-2 Standard (unweighted)
  ├── Glicko-2 MP-Weighted (fractional)
  └── Whole-History Rating (Coulom MAP)
         │
         ▼
[Rating Persistence (data/tta_ratings.db)]
  • player_ratings (current rankings & stats)
  • rating_history (time-series trajectory points)
         │
         ▼
[Flask Presentation Layer (src/web/)]
  • /leaderboard (search, filter, pagination, model toggle)
  • /player/<name> (cards, Chart.js multi-line graph, H2H)
  • /analysis (correlation matrix, histograms, movers)
```

---

## 2. Database Schema (SQLite with WAL Mode)

### `players`
Stores metadata for all 3,489 unique players:
- `player_id`: Integer primary key
- `name`: Unique player handle
- `country_code`: 2-letter ISO 3166-1 alpha-2 code
- `title`: Competitive title (GM = Grandmaster, M = Master, P = Pro)
- `title_count`: Cumulative titles won
- `last_played`: Date string (YYYY-MM-DD)

### `matches`
Raw tournament matches:
- `match_id`: Integer primary key
- `tournament`: Tournament name
- `date`: Date string (YYYY-MM-DD)
- `player_count`: 2, 3, or 4
- `player1..4`, `score1..4`: Participant names and scores

### `pairwise_matches`
Expanded 1v1 encounters with multiplayer fractional weights:
- `pairwise_id`: Integer primary key
- `match_id`: Foreign key referencing matches
- `date`, `tournament`, `player_count`
- `player_a`, `player_b`: Participant handles
- `score_a`, `score_b`: Final match scores
- `outcome_a`: 1.0 (win), 0.5 (draw), 0.0 (loss)
- `weight`: $1.0 / (\text{player\_count} - 1)$

### `player_ratings`
Calculated ratings for each model:
- `model_type`: `'glicko2_std'`, `'glicko2_mp'`, or `'whr'`
- `player_name`: Handle
- `rating`: Scaled rating ($\mu 	imes 173.7178 + 1500$)
- `rd`: Rating deviation ($\phi 	imes 173.7178$)
- `sigma`: Volatility or drift rate
- `c_rating`: Conservative rating ($R - 3 \times RD$)
- `rank`: Leaderboard rank sorted by conservative rating
- `opponents_count`, `wins`, `losses`, `draws`, `win_rate`
- `last_played`: Date string

### `rating_history`
Time-series points for historical profile charts:
- `model_type`: Model identifier
- `player_name`: Handle
- `period_date`: Date string
- `rating`, `rd`, `c_rating`
