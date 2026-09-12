"""Master data and rating pipeline runner for TTA-Glicko2-WHR."""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.db import init_db
from src.data.loader import run_ingestion
from src.models.glicko2.calculator import compute_glicko2_ratings
from src.models.whr.calculator import compute_whr_ratings

def run_all(skip_ingestion=False, formats=None):
    if formats is None:
        formats = [0, 2, 3, 4]  # 0=All, 2=2p, 3=3p, 4=4p

    t_start = time.time()
    print("==========================================================")
    print("   TTA Rating Engine: Master Pipeline Execution          ")
    print("==========================================================")

    init_db()

    if not skip_ingestion:
        print("\n[1/4] Ingesting CSV datasets & generating pairwise matches...")
        run_ingestion()
    else:
        print("\n[1/4] Skipping ingestion (using existing SQLite tables)...")

    for fmt in formats:
        fmt_label = f"{fmt}p" if fmt > 0 else "All (Combined)"
        print(f"\n--- Processing Format: {fmt_label} ---")

        print(f"[{fmt_label}] Computing Glicko-2 Standard...")
        t0 = time.time()
        compute_glicko2_ratings(weighted=False, player_count=fmt)
        print(f"Completed Glicko-2 Standard ({fmt_label}) in {time.time() - t0:.2f}s.")

        print(f"[{fmt_label}] Computing Glicko-2 MP-Weighted...")
        t0 = time.time()
        compute_glicko2_ratings(weighted=True, player_count=fmt)
        print(f"Completed Glicko-2 MP-Weighted ({fmt_label}) in {time.time() - t0:.2f}s.")

        print(f"[{fmt_label}] Computing Whole-History Rating (WHR)...")
        t0 = time.time()
        compute_whr_ratings(player_count=fmt, max_iter=7, tol=1e-3, verbose=True)
        print(f"Completed WHR ({fmt_label}) in {time.time() - t0:.2f}s.")

    total_time = time.time() - t_start
    print("\n==========================================================")
    print(f"   Pipeline Finished Successfully in {total_time:.2f}s!   ")
    print("==========================================================\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run TTA rating pipeline.')
    parser.add_argument('--skip-ingest', action='store_true', help='Skip CSV ingestion and only recompute ratings')
    parser.add_argument('--formats', nargs='+', type=int, default=[0, 2, 3, 4], help='Formats to compute (0=All, 2, 3, 4)')
    args = parser.parse_args()

    run_all(skip_ingestion=args.skip_ingest, formats=args.formats)
