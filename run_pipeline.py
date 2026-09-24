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
from src.data.badges import derive_tournament_badges
from src.models.glicko2.calculator import compute_glicko2_ratings
from src.models.whr.calculator import compute_whr_ratings
from src.models.evaluation.standard_eval import run_standard_calibration_all
from src.models.evaluation.walk_forward import run_walk_forward_all

def run_all(skip_ingestion=False, formats=None):
    if formats is None:
        formats = [0, 2, 3, 4]  # 0=All, 2=2p, 3=3p, 4=4p

    t_start = time.time()
    print("==========================================================")
    print("   TTA Rating Engine: Master Pipeline Execution          ")
    print("==========================================================")

    init_db()

    if not skip_ingestion:
        print("\n[1/5] Ingesting CSV datasets & generating pairwise matches...")
        run_ingestion()
    else:
        print("\n[1/5] Skipping ingestion (using existing SQLite tables)...")

    reset_modes = ['continuous', 'softer']

    print("\n[2/5] Computing Glicko-2 and WHR ratings across formats & reset modes...")
    for fmt in formats:
        fmt_label = f"{fmt}p" if fmt > 0 else "All (Combined)"
        print(f"\n--- Processing Format: {fmt_label} ---")

        for rm in reset_modes:
            print(f"[{fmt_label}] Computing GlickoD* Gold Standard ({rm})...")
            compute_glicko2_ratings(engine='glicko2_daneo', player_count=fmt, reset_mode=rm)

            print(f"[{fmt_label}] Computing Glicko-2 Standard ({rm})...")
            compute_glicko2_ratings(weighted=False, player_count=fmt, reset_mode=rm)

            print(f"[{fmt_label}] Computing Glicko-2 MP-Weighted ({rm})...")
            compute_glicko2_ratings(weighted=True, player_count=fmt, reset_mode=rm)

            print(f"[{fmt_label}] Computing Glicko-2 Adaptive-T ({rm})...")
            compute_glicko2_ratings(engine='glicko2_adapt', player_count=fmt, reset_mode=rm)

            print(f"[{fmt_label}] Computing Whole-History Rating ({rm})...")
            compute_whr_ratings(player_count=fmt, max_iter=6, tol=1e-3, reset_mode=rm, verbose=False)

    print("\n[3/5] Deriving official tournament badges (GM, M, Platinum, Gold, Silver, Bronze, Wood)...")
    titles = derive_tournament_badges()
    print(f"Assigned tournament badges for {len(titles):,} players.")

    print("\n[4/5] Precomputing and caching standard & walk-forward calibration benchmarks...")
    try:
        run_standard_calibration_all(verbose=False)
        print("Standard calibration metrics successfully cached.")
        run_walk_forward_all(verbose=False)
        print("Walk-forward out-of-sample calibration metrics successfully cached.")
    except Exception as e:
        print(f"Note: Calibration precomputation deferred: {e}")

    print("\n[5/5] Refreshing and synchronizing Hall of Fame trophyboards & player achievements...")
    try:
        from src.data.hall_of_fame import derive_hall_of_fame_data
        derive_hall_of_fame_data()
        print("Hall of Fame trophyboards and player achievements synchronized successfully.")
    except Exception as e:
        print(f"Note: Hall of Fame synchronization warning: {e}")

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

