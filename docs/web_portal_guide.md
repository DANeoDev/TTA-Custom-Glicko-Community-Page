# Web Portal User Guide

The Through the Ages (TTA) Rating Portal provides an intuitive, antique-themed web dashboard for analyzing competitive players.

---

## 1. Global Model Switcher
Located in the upper-right corner of the top navigation bar. Clicking any model immediately switches the active rating model across the entire session:
- **Glicko-2 Standard**: Official online leaderboard benchmark (naive 1v1 pairwise).
- **Glicko-2 MP-Weighted**: Scientifically calibrated for 3p and 4p matches with fractional weighting ($w = 1/(N-1)$).
- **Whole-History Rating (WHR)**: Rémi Coulom's retrospective Brownian motion model.

---

## 2. Leaderboard View (`/`)
- **Ranking Column**: Ranked strictly by **Conservative Rating** ($C = \mu - 3\sigma$).
- **Format Selector**: Instantly switch between **All Formats**, **2-Player (Duel)**, **3-Player**, and **4-Player** ratings and leaderboards.
- **Inactivity Filter**: Standard default view hides inactive players (no tournament game in >12 months), with toggles to view all 3,489 competitors or retired players only.
- **RB48 Deltas Filter**: Toggle performance deltas across selectable time windows: **Off**, **Last Month (30d)**, **Last Quarter (90d)**, **Last Year (365d)**, or **Official Baseline**.
- **Hover Explainers**: Interactive tooltips on all table headers explaining C-Rating, RD, W-L-D, Win%, and inactivity.
- **Nationality Flags**: Displays country flags derived from ISO 3166-1 alpha-2 codes.
- **Title Badges**: `GM` (Grandmaster), `M` (Master), `P` (Pro).
- **Interactive Search & Title Filter**: Filter instantly by player name, country code, or title.
- **Sorting & Pagination**: Click any column header to sort ascending or descending.

---

## 3. Player Profile View (`/player/<name>`)
- **Format Switcher**: View career rating and rank in All Formats, 2p, 3p, or 4p.
- **3-Model Summary Cards**: Direct side-by-side comparison of the player's rating, RD, conservative rating, and rank across all 3 models.
- **Historical Trajectory Chart**:
  - Interactive Chart.js graph plotting the player's entire 2017--2026 career evolution.
  - Displays Glicko-2 Standard (Gold), Glicko-2 MP-Weighted (Crimson), and WHR (Azure).
- **Recent Matches Table**: Displays the player's last 30 tournament games with final placement badges (1st, 2nd, 3rd, 4th), scores, and all participant names.
- **Head-to-Head Records**: Table showing records against the player's top 25 rivals.

---

## 4. FAQ & Model Guide (`/faq`)
- Dedicated comprehensive reference guide with tabbed categories:
  - **Rating Models**: Mathematical principles of Glicko-2 and Whole-History Rating.
  - **Conservative Rating (C)**: Formula $C = \mu - 3\sigma$ and volatility suppression.
  - **Multiplayer Weighting**: Coulom fractional match weighting $w = 1/(N-1)$.
  - **Game Formats**: Strategic differences in 2p, 3p, and 4p games.
  - **Inactivity & Retirement**: The 12-month activity rule and unretirement.
  - **RB48 Deltas**: Time windows and delta badges.
  - **Titles**: Grandmaster, Master, and Pro criteria.

---

## 5. Model Analysis & Subpages (`/analysis`)
- **Subpage Navigation Tabs**:
  - **Overview (`/analysis`)**: Cross-Model Agreement Matrix (Spearman Rank Correlation $\rho$, Pearson Correlation $r$), summary statistics, rating density histograms, and calibration chart preview.
  - **Calibration & Reliability (`/analysis/calibration`)**: Detailed reliability diagram comparing predicted vs observed win rates across 10 probability bins with Brier scores and calibration error.
  - **Top Movers & Divergence (`/analysis/movers`)**: Dedicated analysis of players experiencing the largest rank shifts between models (Standard vs MP-Weighted, Standard vs WHR, MP vs WHR), filterable by format and min games.
  - **Activity & Demographics (`/analysis/activity`)**: Community breakdown of active vs inactive players, match volume by format, title holders, and top 15 participating nations.
