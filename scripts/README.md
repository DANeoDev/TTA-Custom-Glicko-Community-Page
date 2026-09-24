# Operational & Pipeline Scripts

This directory contains standalone operational, data-sync, and mathematical optimization utilities for the TTA Rating Engine.

## Operational Scripts

| Script | Purpose | Usage |
|---|---|---|
| `assemble_all_matches.py` | Compiles raw tournament files and match records into the canonical `data/raw/all_matches.csv`. | `python scripts/assemble_all_matches.py` |
| `backfill_replay_codes.py` | Backfills missing CGE digital game codes across matches. | `python scripts/backfill_replay_codes.py` |
| `crawl_ic_s34.py` | Scrapes International Championship Season 34 matches directly from CGE portal. | `python scripts/crawl_ic_s34.py` |
| `optimize_daneo_adaptive_t.py` | Calibrates empirical parameters for the Daneo Adaptive-Tau algorithm using scipy optimization. | `python scripts/optimize_daneo_adaptive_t.py` |
| `precompute_daneo_ratings.py` | Precomputes and writes Daneo Adaptive-Tau rating series directly to database. | `python scripts/precompute_daneo_ratings.py` |
| `precompute_resets.py` | Precomputes ratings under Continuous, Softer, Soft, and Hard reset modes. | `python scripts/precompute_resets.py` |
| `precompute_retro_ratings.py` | Precomputes retro-calibrated rating baselines. | `python scripts/precompute_retro_ratings.py` |

## Archived Scripts (`scripts/archive/`)

Contains one-off diagnostic checks, isolated simulation tests, and historical single-player patches (`test_exact_prior.py`, `check_bins.py`, `trace_tianren.py`, etc.). Retained for auditability and historical reference.
