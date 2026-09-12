# Through the Ages: Tri-Model Rating Engine & Web Portal

A high-performance rating engine and web interface for competitive **Through the Ages (TTA)**, featuring 3 selectable rating systems, country flags, player profiles with historical trajectory charts, and comprehensive model comparative diagnostics.

![Theme Preview](src/web/static/img/favicon.png)

---

## 1. Key Features

- **Tri-Model Rating Architecture**:
  1. **Glicko-2 Standard (Naive Pairwise)**: Preserves 1:1 parity with the official online leaderboard baseline.
  2. **Glicko-2 MP-Weighted (Coulom/Glickman Fractional)**: Variance-calibrated for 3-player and 4-player games ($w = \frac{1}{N-1}$), preventing artificial variance shrinkage and premature overconfidence.
  3. **Whole-History Rating (WHR)**: Rémi Coulom's global retrospective model using Brownian motion random-walk over the entire 2017--2026 timeline.
- **Dedicated Multi-Format Ratings**:
  - Independent rating trackers and leaderboards for **All Formats**, **2-Player Duels**, **3-Player Games**, and **4-Player Games**.
- **Historical Peak Rating & Peak Rank**:
  - Automatically queries the exact date of each player's career peak rating and calculates their historical **Peak Rank** against the field of competitors active on that date.
- **Official Tournament Achievements & Scraper Pipeline**:
  - Ingests and aggregates records from official TTA International, Intermezzo, and Continental championships (`tournaments/` folder).
  - Standalone scraping & sync CLI (`sync_tournaments.py`) with real-time progress, retry fallbacks, and comprehensive summary stats.
  - Dedicated player tournament achievements subpages (`/player/<name>/achievements`) with sortable columns and championship honors.
- **Interactive Head-to-Head (H2H) Match Explorer**:
  - Fast opponent search and dedicated H2H modal viewer powered by the `/api/h2h/<p1>/<p2>` endpoint.
- **Antique Civilization Aesthetic**:
  - Themed with Cinzel and Marcellus typography, warm dark parchment palette (`#1c130d`), gold accents (`#e5a93c`), crimson highlights (`#8e1e1d`), edge-aware tooltips, and circular navigation icons.
- **Offline Nationality Flags**:
  - Automatically parses ISO 3166-1 alpha-2 codes and renders clean country flags for all 3,489 competitive players.
- **Blazing Fast Pipeline**:
  - Ingests 131,424 matches and expands 376,425 pairwise encounters into SQLite in ~7 seconds.
  - Computes full 9-year Glicko-2 Standard, MP-Weighted, and WHR ratings in under 40 seconds total.

---

## 2. Quickstart Guide

### Prerequisites
- Python 3.10+
- Dependencies: `Flask`, `numpy`, `pandas`, `requests`, `pytest`

```bash
pip install -r requirements.txt
```

### Ingest Data & Compute Ratings
```bash
# Run the master pipeline (ingests CSVs and computes all 3 rating models across all formats)
python run_pipeline.py

# If data is already in SQLite, quickly recompute ratings:
python run_pipeline.py --skip-ingest
```

### Sync Tournament Achievements & Scrape Live Sources
```bash
# Ingest local tournament sheets or scrape online tournament data sources:
python sync_tournaments.py

# Skip remote network fetches and build directly from local tournament files:
python sync_tournaments.py --local-only
```

### Launch Web Portal
```bash
python run_web.py
```
Open your browser at: **`http://127.0.0.1:5050`**

### Run Test Suite
```bash
pytest tests -v
```

---

## 3. Project Structure

```
TTA-Glicko2-WHR/
├── data/
│   ├── raw/
│   │   ├── all_matches.csv          # 131,424 competitive tournament matches
│   │   └── ratings_overall.csv      # Online leaderboard benchmark snapshot
│   └── tta_ratings.db               # SQLite database with indexed tables
├── src/
│   ├── data/
│   │   ├── db.py                    # SQLite schema and connection helpers
│   │   └── loader.py                # Fast CSV ingestion & pairwise expander
│   ├── models/
│   │   ├── glicko2/
│   │   │   ├── engine.py            # Standard & MP-weighted Glicko-2 math
│   │   │   └── calculator.py        # 14-day time-period batch runner
│   │   └── whr/
│   │       ├── solver.py            # Thomas tridiagonal linear system solver
│   │       ├── engine.py            # Coulom WHR MAP Newton-Raphson estimator
│   │       └── calculator.py        # Historical trajectory persistence
│   └── web/
│       ├── app.py                   # Flask application factory
│       ├── routes/
│       │   ├── leaderboard.py       # Leaderboard with 3-model switch
│       │   ├── player.py            # Player profiles, charts & H2H records
│       │   └── analysis.py          # Model diagnostics & correlation matrix
│       ├── static/
│       │   ├── css/styles.css       # Antique visual styling
│       │   └── img/                 # Background, favicon, home button
│       └── templates/
│           ├── base.html            # Thematic shell & navigation
│           ├── leaderboard.html     # Paginated table with flags & titles
│           ├── player.html          # Profile with 3-curve trajectory chart
│           └── analysis.html        # Cross-model comparative diagnostics
├── tests/
│   ├── test_glicko2.py              # Glickman paper verification & MP weighting
│   ├── test_pairwise.py             # Match decomposition verification (DireNTropy)
│   ├── test_whr.py                  # Thomas solver & WHR convergence
│   └── test_web.py                  # Flask route & model switcher integration
├── docs/                            # Comprehensive documentation suite
│   ├── index.md
│   ├── mathematics.md               # Rigorous rating formula derivations
│   ├── architecture.md              # Database schemas & pipeline flow
│   ├── cli_reference.md             # Command-line usage manual
│   └── web_portal_guide.md          # User portal navigation guide
├── run_pipeline.py                  # Master pipeline execution CLI
├── run_web.py                       # Web server runner CLI
├── pyproject.toml
└── requirements.txt
```

---

## 4. Documentation Suite

Explore the comprehensive guides in the `docs/` folder:
- [Mathematics & Formulas](docs/mathematics.md)
- [System Architecture](docs/architecture.md)
- [CLI Reference](docs/cli_reference.md)
- [Web Portal Guide](docs/web_portal_guide.md)
