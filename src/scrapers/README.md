# Match Scrapers & Tournament Data Ingestion (`src/scrapers`)

This directory contains scraping harnesses, tournament discovery scripts, and data connectors for fetching competitive **Through the Ages** match logs from online servers and community spreadsheets.

---

## 1. Overview

Competitive Through the Ages matches originate from multiple distinct sources:
- The **Czech Games Edition (CGE)** official digital app backend.
- Community-maintained Google Sheets and Challonge tournament brackets.
- Historical archives from the International Championship, Intermezzo, and Royal League organizers.

The `src/scrapers` package manages the extraction and initial normalization of these sources prior to database insertion.

---

## 2. Module Breakdown

### `cge.py` &mdash; Official CGE App Scraper
- Interfaces with the CGE game log endpoints.
- Handles user session authentication, rate-limiting, and automatic retry backoff.
- Retrieves match metadata:
  - Game ID and timestamp
  - Player IDs, names, and finishing rank
  - Raw cultural point scores and civil resignations
  - Game configuration (Base Game vs. Leaders & Wonders expansion, digital timer rules)

### `discovery.py` &mdash; Automated Tournament & League Discovery
- Inspects known Google Sheets and community links for newly concluded tournament seasons.
- Identifies division tiers (e.g. Emperor, King, Grandmaster, Master, Platinum, Gold, Silver, Bronze, Wood).
- Extracts final player placements and medal assignments into structured staging files.

### `sources.py` &mdash; Source Definitions & Configuration
- Central registry of all upstream URLs, sheet identifiers, API endpoints, and season mapping tables.
- Validates source schemas against expected column headers before parsing starts.

---

## 3. Data Pipeline Flow

```
[CGE Server / Community Sheets]
              │
              ▼
    [src/scrapers/cge.py]
    [src/scrapers/discovery.py]
              │
              ▼ (Staging JSON / CSV)
    [src/data/loader.py]
              │
              ▼
    [data/tta_ratings.db]
```

---

## 4. Usage

To run the tournament discovery process:

```bash
python -m src.scrapers.discovery
```

To fetch recent games from the CGE API endpoint:

```bash
python -m src.scrapers.cge --recent
```
