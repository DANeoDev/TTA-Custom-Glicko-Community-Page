import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.glicko2.calculator import compute_glicko2_ratings
from src.models.whr.calculator import compute_whr_ratings

def main():
    print("Precomputing Golden Ratio Season Resets across all models and formats...")
    t0 = time.time()
    
    formats = [0, 2, 3, 4]
    resets = ['soft', 'amplified']

    for r in resets:
        for fmt in formats:
            print(f"\n--- Reset Mode: {r} | Format: {fmt} ---")
            
            print(f"Computing Glicko-2 Standard ({r})...")
            compute_glicko2_ratings(weighted=False, player_count=fmt, reset_mode=r)
            
            print(f"Computing Glicko-2 Multiplayer ({r})...")
            compute_glicko2_ratings(weighted=True, player_count=fmt, reset_mode=r)
            
            print(f"Computing WHR ({r})...")
            compute_whr_ratings(player_count=fmt, reset_mode=r)

    print(f"\n[DONE] Precomputations completed in {time.time() - t0:.2f}s")

if __name__ == '__main__':
    main()
