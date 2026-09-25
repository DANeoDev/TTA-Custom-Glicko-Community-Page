# Through the Ages: Rating Engine & Web Portal

A high-performance rating engine and web interface for competitive **Through the Ages (TTA)**, featuring 5 selectable rating engines, Golden-Ratio season reset regimes, country flags, player profiles with historical trajectory charts, official tournament trophyboards, and comprehensive predictive calibration diagnostics.

![Theme Preview](src/web/static/img/favicon.png)

---

## 1. Key Features

- **Multi-Model Rating Architecture**:
  1. **GlickoD (`glicko2_daneo`)**: The empirical gold standard model combining Golden Ratio ($\phi$) multiplayer information decomposition with 15-game emergent prior recalibration, achieving superior predictive Brier scores and ECE calibration across multiplayer lobbies.
  2. **Glicko-2 Standard (`glicko2_std`)**: Preserves 1:1 parity with the official online leaderboard baseline.
  3. **Glicko-2 MP-Weighted (`glicko2_mp`)**: Variance-calibrated for 3-player and 4-player games ($w = \frac{1}{N-1}$), preventing artificial variance shrinkage and premature overconfidence.
  4. **Glicko-2 Adaptive-T (`glicko2_adapt`)**: Score-margin-calibrated expectations for high-accuracy predictions.
  5. **Whole-History Rating (`whr`)**: Rémi Coulom's global retrospective model using Brownian motion random-walk over the entire 2017--2026 timeline.
- **Season Reset Regimes**:
  - **Continuous**: Unbroken 9-year career progression.
  - **Softer Reset**: Golden Ratio ($\phi$) uncertainty inflation ($\alpha$) and mean deflation ($\lambda$) preserving career momentum while re-opening upward mobility.
  - **Soft & Hard Resets**: Traditional annual season reset baselines.
- **Dedicated Multi-Format Ratings**:
  - Independent rating trackers and leaderboards for **All Formats**, **2-Player Duels**, **3-Player Games**, and **4-Player Games**.
- **Community Leaderboard & Hall of Fame**:
  - Official **Community Standard Leaderboard** featuring Wolvs' Best-8 rolling point system (`/community`).
  - **Hall of Fame Hub & Trophyboards** celebrating historic champions across International Championship (4P), Intermezzo (3P), Royal League (2P), and World Championship (`/hall_of_fame`).
- **Admin Dashboard & CMS**:
  - Secure webmaster portal (`/admin/dashboard`) for real-time tournament ingestion, dataset merging, player alias reconciliation, and live CGE scraper controls.
- **Antique Civilization Aesthetic**:
  - Themed with Cinzel and Marcellus typography, warm dark parchment palette (`#1c130d`), gold accents (`#e5a93c`), crimson highlights (`#8e1e1d`), edge-aware tooltips, and circular navigation icons.
- **Offline Nationality Flags**:
  - Automatically parses ISO 3166-1 alpha-2 codes and renders clean country flags for all competitive players.
- **Blazing Fast Pipeline**:
  - Ingests 131,000+ matches and expands 376,000+ pairwise encounters into SQLite in ~7 seconds.
  - Computes multi-model ratings across all formats in under a minute.

---

## 2. Quickstart Guide

### Prerequisites
- Python 3.10+
- Dependencies: `Flask`, `numpy`, `pandas`, `requests`, `pytest`, `beautifulsoup4`, `python-dotenv`, `openpyxl`

```bash
pip install -r requirements.txt
```

### Ingest Data & Compute Ratings
```bash
# Run the master pipeline (ingests CSVs and computes rating models across formats)
python run_pipeline.py

# If data is already in SQLite, quickly recompute ratings:
python run_pipeline.py --skip-ingest
```

### Sync Tournament Achievements & Scrape Live Sources
```bash
# Ingest local tournament sheets or scrape online tournament data sources:
python sync_tournaments.py
```

### Launch Web Portal
```bash
python run_web.py
```
Open your browser at: **`http://127.0.0.1:5050`**

### Run Test Suite
```bash
# Fast unit & integration tests:
pytest tests -m "not slow"

# Full comprehensive test suite (including mathematical convergence sweeps):
pytest tests
```

---

## 3. Project Structure

```
TTA-Glicko2-WHR/
├── data/
│   ├── raw/                         # Raw tournament CSVs and matches
│   ├── tournaments/                 # Championship data, Google Sheets configs & rules
│   └── tta_ratings.db               # SQLite database with indexed tables
├── src/
│   ├── data/
│   │   ├── db.py                    # SQLite schema, migrations & connection helpers
│   │   ├── loader.py                # CSV ingestion & pairwise expander
│   │   ├── badges.py                # Tournament badge and title assigner
│   │   ├── hall_of_fame.py          # Hall of fame trophyboards & achievements
│   │   └── merger.py                # Automated dataset merger & deduplicator
│   ├── models/
│   │   ├── glicko2/                 # Standard, MP-Weighted & Adaptive-Tau Glicko-2
│   │   ├── whr/                     # Coulom WHR MAP Newton-Raphson & Thomas solver
│   │   └── evaluation/              # Standard & Walk-forward calibration benchmarks
│   ├── scrapers/                    # CGE portal scrapers & tournament discovery
│   └── web/
│       ├── app.py                   # Flask application factory
│       ├── routes/                  # Blueprints (leaderboard, player, analysis, admin, etc.)
│       ├── static/                  # CSS styling, flags, and image assets
│       └── templates/               # Antique parchment Jinja templates
├── scripts/                         # Operational data & optimization utilities
│   ├── archive/                     # Historical investigation & one-off diagnostic scripts
│   └── README.md                    # Script catalog and usage instructions
├── tests/                           # Comprehensive automated test suite (125 tests)
├── docs/                            # Documentation suite
├── run_pipeline.py                  # Master pipeline execution CLI
├── run_web.py                       # Web server runner CLI
├── sync_tournaments.py              # Tournament data synchronization CLI
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

