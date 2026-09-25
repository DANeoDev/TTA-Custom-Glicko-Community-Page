#!/usr/bin/env python3
"""
scripts/prune_db_for_production.py

Creates an optimized, production-ready SQLite database for PythonAnywhere Free Tier hosting.
Reduces the 1.4 GB database down to ~400 MB (zipped ~98 MB) without losing ANY active website feature:
- Retains all 16 UI models across all 4 formats (0p/2p/3p/4p).
- Retains all calibration curves and walk-forward metrics.
- Retains all match records, tournament achievements, and Head-to-Head histories.
- Retains full career timelines for all chart models.
- Removes abandoned experimental models and redundant indexes.
"""

import os
import shutil
import sqlite3
import zipfile
import time

SOURCE_DB = "data/tta_ratings.db"
TARGET_DB = "data/tta_ratings_prod.db"
TARGET_ZIP = "data/tta_ratings_prod.zip"

def prune():
    start_time = time.time()
    print(f"Starting production database pruning...")
    print(f"Source: {SOURCE_DB} ({os.path.getsize(SOURCE_DB) / (1024*1024):.2f} MB)")

    # 1. Copy source to target
    if os.path.exists(TARGET_DB):
        os.remove(TARGET_DB)
    shutil.copy2(SOURCE_DB, TARGET_DB)
    print(f"Copied to temporary working file: {TARGET_DB}")

    conn = sqlite3.connect(TARGET_DB)
    cursor = conn.cursor()

    # 2. Delete abandoned experimental models from player_ratings & calibration
    abandoned_patterns = ['%_soft', '%_amplified', '%_soft_retro', '%_amplified_retro']
    for pat in abandoned_patterns:
        cursor.execute("DELETE FROM player_ratings WHERE model_type LIKE ?;", (pat,))
        cursor.execute("DELETE FROM standard_calibration WHERE model_type LIKE ?;", (pat,))
        cursor.execute("DELETE FROM walk_forward_calibration WHERE model_type LIKE ?;", (pat,))
        cursor.execute("DELETE FROM rating_history WHERE model_type LIKE ?;", (pat,))

    # 3. Retain the 5 primary base chart models in rating_history
    # (Full trajectories for glicko2_std, glicko2_mp, glicko2_adapt, whr, glicko2_daneo)
    chart_models = (
        'glicko2_std',
        'glicko2_mp',
        'glicko2_adapt',
        'whr',
        'glicko2_daneo'
    )
    placeholders = ','.join(['?'] * len(chart_models))
    cursor.execute(f"DELETE FROM rating_history WHERE model_type NOT IN ({placeholders});", chart_models)

    # 4. Drop redundant or offline-only indexes
    print("Dropping redundant indexes...")
    cursor.execute("DROP INDEX IF EXISTS idx_rh_player;")       # Covered by idx_rh_player_fast
    cursor.execute("DROP INDEX IF EXISTS idx_pw_match_id;")     # Offline update script only
    cursor.execute("DROP INDEX IF EXISTS idx_pw_date;")         # Offline pipeline only

    conn.commit()

    # 5. Optimize and Vacuum
    print("Executing PRAGMA optimize and VACUUM...")
    cursor.execute("PRAGMA optimize;")
    conn.commit()
    cursor.execute("VACUUM;")
    conn.close()

    db_size = os.path.getsize(TARGET_DB) / (1024*1024)
    print(f"Pruned DB size: {db_size:.2f} MB")

    # 6. Compress to ZIP for lightning-fast upload
    print(f"Creating compressed upload package: {TARGET_ZIP}...")
    if os.path.exists(TARGET_ZIP):
        os.remove(TARGET_ZIP)

    with zipfile.ZipFile(TARGET_ZIP, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(TARGET_DB, arcname="tta_ratings.db")

    zip_size = os.path.getsize(TARGET_ZIP) / (1024*1024)
    elapsed = time.time() - start_time
    print(f"Done in {elapsed:.1f}s!")
    print(f"Final Production DB: {TARGET_DB} ({db_size:.2f} MB)")
    print(f"Final Upload ZIP:    {TARGET_ZIP} ({zip_size:.2f} MB)")

if __name__ == "__main__":
    prune()
