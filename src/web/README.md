# Web Application Architecture (`src/web`)

This directory contains the Flask-based web application and presentation layer for the **Through the Ages (TTA) Rating Portal**.

---

## 1. Architecture Overview

The web application is built with Python Flask and renders server-side Jinja2 templates enriched with interactive Chart.js visualizations.

```
                  [Flask App Factory (app.py)]
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
 [Blueprints]         [Context Processors]     [Jinja2 Templates]
 - leaderboard.py     - get_title_name()       - leaderboard.html
 - player.py          - get_flag()             - player.html
 - analysis.py        - cms_blocks             - player_matrix.html
 - faq.py                                      - player_achievements.html
 - admin.py                                    - faq.html
                                               - analysis.html
```

---

## 2. Directory Structure

- `app.py` &mdash; Application factory, route registration, global Jinja context processors (`get_title_name`, `get_flag`), error handlers, and caching headers.
- `routes/` &mdash; Modular Flask blueprints:
  - `leaderboard.py`: Competitive leaderboard table, engine switching (`GlickoD`, `Glicko-2 Std`, `MP`, `Adapt`, `WHR`), format filtering (All, Duel, 3P, 4P), active/retired status toggles, and live search prefiltering.
  - `player.py`: Detailed player dossiers, head-to-head match histories, unified interactive rating trajectory charts (supporting live toggles for **Continuous vs. Season Reset** and **Expected Mean vs. Conservative**), cross-model comparison matrix, and tournament achievements.
  - `analysis.py`: System-wide model comparisons, walk-forward calibration curves, calibration reliability bins, activity distributions, and biggest rating movers.
  - `faq.py`: Interactive documentation tabs, mathematical derivations, Gaussian tail equations, and season reset guides.
  - `admin.py`: Webmaster administration panel, CMS content block overrides, database consistency verification, and manual match corrections.
  - `tournaments.py`: Tournament hub, division breakdown tables, and season archives.
  - `community.py`: Community leaderboard and historical hall of fame listings.
- `templates/` &mdash; Jinja2 HTML templates styled with medieval antique board game aesthetic.
- `static/` &mdash; CSS stylesheets, custom JavaScript modules, Chart.js bundles, and SVG flag assets for 50+ nations.

---

## 3. Key Frontend Features

### Dual-Dimension Trajectory Switcher
On player profiles (`player.html`), competitors can inspect their rating history across two orthogonal dimensions without page reloads:
1. **Mode**: `Continuous (Career)` vs. `Season Reset (Annual Soft Reset)`.
2. **Curve**: `Expected Mean (E = R)` vs. `Conservative (C = R - 2*RD)`.

### Graceful Empty-State Protection
If a player has no recorded matches in a specific format (e.g. 2-Player Duel), the chart container displays an informative fallback notice instead of rendering an uninitialized or broken canvas.

### Official Badge & Title Presentation
- Badges strictly display active competitive titles earned within the last 12 months.
- The `Super GM` (`👑 GM` / `.badge-sgm`) badge is awarded to winners of the top division in the International Championship, Intermezzo Championship, or Royal League.
- Historical peak ranks (`Peak Rank: [Badge]`) are highlighted exclusively on player profile pages.

---

## 4. Running the Development Server

To start the local web application:

```bash
python -m src.web.app
```

The portal will be accessible locally at `http://127.0.0.1:5000/`.
