import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.glicko2.calculator import compute_glicko2_ratings
from src.models.evaluation.standard_eval import run_standard_calibration_all

def main():
    print('=================================================================')
    print('Precomputing Retrospective Prior Calibration (Option A) Models')
    print('=================================================================')
    t0 = time.time()
    
    formats = [0, 2, 3, 4]
    engines = [
        ('glicko2_adapt', 'Adaptive-T'),
        ('glicko2_mp', 'MP-Weighted'),
        ('glicko2_std', 'Standard')
    ]
    resets = ['continuous', 'softer']

    # Step 1: Precompute Ratings in DB
    total_runs = len(engines) * len(resets) * len(formats)
    current_run = 0

    for eng, eng_name in engines:
        for r in resets:
            for fmt in formats:
                current_run += 1
                fmt_label = f'{fmt}P' if fmt > 0 else 'All'
                print(f'[{current_run}/{total_runs}] Computing {eng_name} ({r}) format={fmt_label} with Retro Prior...')
                compute_glicko2_ratings(
                    engine=eng,
                    reset_mode=r,
                    player_count=fmt,
                    retro_calibrated=True,
                    calibration_threshold=15
                )

    print(f'\nAll rating calculations finished in {time.time() - t0:.2f}s')
    
    # Step 2: Compute Standard Calibration metrics for all retro models
    print('\nRunning Standard Calibration evaluations for Retro models...')
    t_cal = time.time()
    retro_model_keys = [
        f'{eng}_{r}_retro' if r != 'continuous' else f'{eng}_retro'
        for eng, _ in engines
        for r in resets
    ]
    run_standard_calibration_all(formats=formats, model_filter=set(retro_model_keys), verbose=True)
    print(f'\nStandard calibration completed in {time.time() - t_cal:.2f}s')
    print(f'Total time: {time.time() - t0:.2f}s')

if __name__ == '__main__':
    main()
