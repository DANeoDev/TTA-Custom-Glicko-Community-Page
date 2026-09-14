"""Walk-forward (leak-free out-of-sample t+1) calibration and predictive benchmark engine."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

from src.data.db import get_connection
from src.models.whr.engine import WHREngine, GLICKO2_SCALE, DEFAULT_RATING
from src.models.glicko2.engine import Rating, update_rating, GLICKO2_SCALE as G2_SCALE
from src.models.glicko2.calculator import CALIBRATED_TAU, CALIBRATED_SIGMA, INACTIVITY_DRIFT_PER_MONTH

BIN_LABELS = ['50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
IDEAL_POINTS = [0.55, 0.65, 0.75, 0.85, 0.95]
BIN_EDGES = np.linspace(0.5, 1.0, 6)
NUM_BINS = len(BIN_LABELS)


def compute_metrics_from_preds(preds: List[float], actuals: List[float]) -> Dict[str, Any]:
    """Computes Brier score, ECE, log loss, accuracy, and bin data from probability predictions."""
    if not preds:
        return {
            'matches': 0,
            'brier': 0.25,
            'ece': 0.0,
            'ece_pct': 0.0,
            'log_loss': 0.6931,
            'accuracy': 0.5,
            'bin_data': {
                'labels': BIN_LABELS,
                'ideal': IDEAL_POINTS,
                'actuals': IDEAL_POINTS,
                'preds': IDEAL_POINTS,
                'counts': [0] * NUM_BINS
            }
        }

    p_arr = np.array(preds, dtype=float)
    y_arr = np.array(actuals, dtype=float)
    n = len(p_arr)

    # 1. Brier Score (MSE)
    brier = float(np.mean((p_arr - y_arr) ** 2))

    # 2. Binary Accuracy (treating 0.5 draws as 0.5 point)
    correct = np.sum((p_arr > 0.5) & (y_arr > 0.5)) + 0.5 * np.sum(y_arr == 0.5)
    accuracy = float(correct / n)

    # 3. Log Loss (cross-entropy with epsilon clipping)
    eps = 1e-7
    p_clipped = np.clip(p_arr, eps, 1.0 - eps)
    ll = float(-np.mean(y_arr * np.log(p_clipped) + (1.0 - y_arr) * np.log(1.0 - p_clipped)))

    # 4. Bin Frequencies & ECE
    bin_actuals = []
    bin_preds = []
    bin_counts = []
    for i in range(NUM_BINS):
        low, high = BIN_EDGES[i], BIN_EDGES[i + 1]
        mask = (p_arr >= low) & (p_arr < high if i < NUM_BINS - 1 else p_arr <= high)
        cnt = int(np.sum(mask))
        bin_counts.append(cnt)
        if cnt > 0:
            bin_actuals.append(round(float(np.mean(y_arr[mask])), 4))
            bin_preds.append(round(float(np.mean(p_arr[mask])), 4))
        else:
            mid = round(float((low + high) / 2), 4)
            bin_actuals.append(mid)
            bin_preds.append(mid)

    ece = 0.0
    for i in range(NUM_BINS):
        cnt = bin_counts[i]
        if cnt > 0:
            ece += (cnt / n) * abs(bin_actuals[i] - bin_preds[i])

    return {
        'matches': n,
        'brier': round(brier, 4),
        'ece': round(ece, 4),
        'ece_pct': round(ece * 100.0, 2),
        'log_loss': round(ll, 4),
        'accuracy': round(accuracy * 100.0, 2),
        'bin_data': {
            'labels': BIN_LABELS,
            'ideal': IDEAL_POINTS,
            'actuals': bin_actuals,
            'preds': bin_preds,
            'counts': bin_counts
        }
    }


def run_walk_forward_evaluation(
    player_count: int = 0,
    start_eval_month: str = '2022-01',
    db_path: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """Executes a monthly expanding-window walk-forward evaluation across all models."""
    conn = get_connection(db_path)
    try:
        fmt_label = f"{player_count}p" if player_count > 0 else "All Formats"
        if verbose:
            print(f"\n=======================================================")
            print(f"Starting Walk-Forward Calibration: {fmt_label} (Start: {start_eval_month})")
            print(f"=======================================================")

        # Load chronological matches
        if player_count and player_count > 0:
            rows = conn.execute("""
                SELECT date, player_a, player_b, outcome_a, weight, player_count
                FROM pairwise_matches
                WHERE player_count = ? AND glicko_eligible = 1
                ORDER BY date, pairwise_id
            """, (player_count,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT date, player_a, player_b, outcome_a, weight, player_count
                FROM pairwise_matches
                WHERE glicko_eligible = 1
                ORDER BY date, pairwise_id
            """).fetchall()

        if verbose:
            print(f"Loaded {len(rows)} eligible pairwise matches.")

        # Group matches by calendar month YYYY-MM
        month_matches = defaultdict(list)
        for r in rows:
            m = r['date'][:7]
            month_matches[m].append(r)

        sorted_months = sorted(month_matches.keys())
        eval_months = [m for m in sorted_months if m >= start_eval_month]
        burn_in_months = [m for m in sorted_months if m < start_eval_month]

        if verbose:
            print(f"Burn-in period: {len(burn_in_months)} months ({burn_in_months[0]} to {burn_in_months[-1]})")
            print(f"Evaluation period: {len(eval_months)} months ({eval_months[0]} to {eval_months[-1]})")

        # Models under test
        models = ['glicko2_std', 'glicko2_mp', 'whr']

        # Rating states
        g2_std_ratings = defaultdict(lambda: Rating(1500.0, 350.0, CALIBRATED_SIGMA))
        g2_mp_ratings = defaultdict(lambda: Rating(1500.0, 350.0, CALIBRATED_SIGMA))
        whr = WHREngine(w2_per_day=0.005)

        # 1. Execute Burn-in Phase
        if verbose:
            print("Processing burn-in phase...")

        for m in burn_in_months:
            m_rows = month_matches[m]

            # Glicko-2 Std & MP
            enc_std = defaultdict(list)
            enc_mp = defaultdict(list)
            for r in m_rows:
                pa, pb, out, w = r['player_a'], r['player_b'], r['outcome_a'], r['weight']
                enc_std[pa].append((g2_std_ratings[pb], out, 1.0))
                enc_std[pb].append((g2_std_ratings[pa], 1.0 - out, 1.0))
                enc_mp[pa].append((g2_mp_ratings[pb], out, w))
                enc_mp[pb].append((g2_mp_ratings[pa], 1.0 - out, w))
                whr.add_game(r['date'], pa, pb, out, w)

            active_std = set(enc_std.keys())
            for p, enc in enc_std.items():
                g2_std_ratings[p] = update_rating(g2_std_ratings[p], enc, tau=CALIBRATED_TAU, weighted=False)
            for p in list(g2_std_ratings.keys()):
                if p not in active_std and g2_std_ratings[p].rd < 350.0:
                    r_cur = g2_std_ratings[p]
                    phi_new = (r_cur.phi**2 + INACTIVITY_DRIFT_PER_MONTH**2)**0.5
                    g2_std_ratings[p] = Rating(r_cur.rating, min(350.0, phi_new * G2_SCALE), r_cur.sigma)

            active_mp = set(enc_mp.keys())
            for p, enc in enc_mp.items():
                g2_mp_ratings[p] = update_rating(g2_mp_ratings[p], enc, tau=CALIBRATED_TAU, weighted=True)
            for p in list(g2_mp_ratings.keys()):
                if p not in active_mp and g2_mp_ratings[p].rd < 350.0:
                    r_cur = g2_mp_ratings[p]
                    phi_new = (r_cur.phi**2 + INACTIVITY_DRIFT_PER_MONTH**2)**0.5
                    g2_mp_ratings[p] = Rating(r_cur.rating, min(350.0, phi_new * G2_SCALE), r_cur.sigma)

        # Fit WHR burn-in to convergence
        if burn_in_months:
            whr.fit(max_iter=7, tol=1e-3, verbose=False)
            if verbose:
                print("Burn-in complete.")

        # Data collection for evaluation
        monthly_results = defaultdict(dict)
        overall_preds = {m: [] for m in models}
        overall_actuals = {m: [] for m in models}

        # 2. Walk-Forward Expanding Evaluation Loop
        for idx, tm in enumerate(eval_months):
            m_matches = month_matches[tm]
            if not m_matches:
                continue

            # (A) Pure Out-of-Sample Predictions for month tm
            month_preds = {m: [] for m in models}
            month_actuals = {m: [] for m in models}

            for r in m_matches:
                pa, pb, out, w = r['player_a'], r['player_b'], r['outcome_a'], r['weight']

                # G2 Std
                ra_std, rb_std = g2_std_ratings[pa].rating, g2_std_ratings[pb].rating
                p_std = 1.0 / (1.0 + 10.0 ** (-(ra_std - rb_std) / 400.0))
                if p_std >= 0.5:
                    month_preds['glicko2_std'].append(p_std)
                    month_actuals['glicko2_std'].append(out)
                else:
                    month_preds['glicko2_std'].append(1.0 - p_std)
                    month_actuals['glicko2_std'].append(1.0 - out)

                # G2 MP
                ra_mp, rb_mp = g2_mp_ratings[pa].rating, g2_mp_ratings[pb].rating
                p_mp = 1.0 / (1.0 + 10.0 ** (-(ra_mp - rb_mp) / 400.0))
                if p_mp >= 0.5:
                    month_preds['glicko2_mp'].append(p_mp)
                    month_actuals['glicko2_mp'].append(out)
                else:
                    month_preds['glicko2_mp'].append(1.0 - p_mp)
                    month_actuals['glicko2_mp'].append(1.0 - out)

                # WHR (ratings strictly prior to observing month tm)
                cur_a = whr.get_current_rating(pa)
                cur_b = whr.get_current_rating(pb)
                ra_whr = cur_a[0] if cur_a else 1500.0
                rb_whr = cur_b[0] if cur_b else 1500.0
                p_whr = 1.0 / (1.0 + 10.0 ** (-(ra_whr - rb_whr) / 400.0))
                if p_whr >= 0.5:
                    month_preds['whr'].append(p_whr)
                    month_actuals['whr'].append(out)
                else:
                    month_preds['whr'].append(1.0 - p_whr)
                    month_actuals['whr'].append(1.0 - out)

            # Record monthly metrics
            for m in models:
                res_m = compute_metrics_from_preds(month_preds[m], month_actuals[m])
                monthly_results[tm][m] = res_m
                overall_preds[m].extend(month_preds[m])
                overall_actuals[m].extend(month_actuals[m])

            if verbose and (idx % 6 == 0 or idx == len(eval_months) - 1):
                b_std = monthly_results[tm]['glicko2_std']['brier']
                b_mp = monthly_results[tm]['glicko2_mp']['brier']
                b_whr = monthly_results[tm]['whr']['brier']
                print(f"[{idx+1}/{len(eval_months)}] Month {tm} ({len(m_matches):5d} games) | Brier -> G2 Std: {b_std:.4f}, G2 MP: {b_mp:.4f}, WHR: {b_whr:.4f}")

            # (B) Incremental Online Update for month tm matches
            # WHR incremental update
            for r in m_matches:
                whr.add_game(r['date'], r['player_a'], r['player_b'], r['outcome_a'], r['weight'])
            whr.fit(max_iter=3, tol=1e-3, verbose=False)

            # Glicko-2 updates
            enc_std = defaultdict(list)
            enc_mp = defaultdict(list)
            for r in m_matches:
                pa, pb, out, w = r['player_a'], r['player_b'], r['outcome_a'], r['weight']
                enc_std[pa].append((g2_std_ratings[pb], out, 1.0))
                enc_std[pb].append((g2_std_ratings[pa], 1.0 - out, 1.0))
                enc_mp[pa].append((g2_mp_ratings[pb], out, w))
                enc_mp[pb].append((g2_mp_ratings[pa], 1.0 - out, w))

            active_std = set(enc_std.keys())
            for p, enc in enc_std.items():
                g2_std_ratings[p] = update_rating(g2_std_ratings[p], enc, tau=CALIBRATED_TAU, weighted=False)
            for p in list(g2_std_ratings.keys()):
                if p not in active_std and g2_std_ratings[p].rd < 350.0:
                    r_cur = g2_std_ratings[p]
                    phi_new = (r_cur.phi**2 + INACTIVITY_DRIFT_PER_MONTH**2)**0.5
                    g2_std_ratings[p] = Rating(r_cur.rating, min(350.0, phi_new * G2_SCALE), r_cur.sigma)

            active_mp = set(enc_mp.keys())
            for p, enc in enc_mp.items():
                g2_mp_ratings[p] = update_rating(g2_mp_ratings[p], enc, tau=CALIBRATED_TAU, weighted=True)
            for p in list(g2_mp_ratings.keys()):
                if p not in active_mp and g2_mp_ratings[p].rd < 350.0:
                    r_cur = g2_mp_ratings[p]
                    phi_new = (r_cur.phi**2 + INACTIVITY_DRIFT_PER_MONTH**2)**0.5
                    g2_mp_ratings[p] = Rating(r_cur.rating, min(350.0, phi_new * G2_SCALE), r_cur.sigma)

        # 3. Overall Aggregate Metrics
        aggregated_results = {}
        for m in models:
            aggregated_results[m] = compute_metrics_from_preds(overall_preds[m], overall_actuals[m])

        if verbose:
            print(f"\n--- Walk-Forward Summary ({fmt_label}) ---")
            for m in models:
                agg = aggregated_results[m]
                print(f"Model: {m:12s} | Out-of-Sample Brier: {agg['brier']:.4f} | ECE: {agg['ece_pct']:.2f}% | LogLoss: {agg['log_loss']:.4f} | Acc: {agg['accuracy']:.1f}%")

        # 4. Save to Database
        with conn:
            # Clear previous entries for this player_count format
            conn.execute("DELETE FROM walk_forward_calibration WHERE player_count = ?", (player_count,))

            # Insert aggregated summary records
            for m in models:
                agg = aggregated_results[m]
                conn.execute("""
                    INSERT INTO walk_forward_calibration 
                    (model_type, player_count, period_month, matches_evaluated, brier_score, ece, log_loss, accuracy, bin_data_json)
                    VALUES (?, ?, 'AGGREGATED', ?, ?, ?, ?, ?, ?)
                """, (
                    m, player_count, agg['matches'], agg['brier'], agg['ece'],
                    agg['log_loss'], agg['accuracy'], json.dumps(agg['bin_data'])
                ))

            # Insert individual monthly records
            for tm, m_data in monthly_results.items():
                for m in models:
                    item = m_data[m]
                    conn.execute("""
                        INSERT INTO walk_forward_calibration 
                        (model_type, player_count, period_month, matches_evaluated, brier_score, ece, log_loss, accuracy, bin_data_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m, player_count, tm, item['matches'], item['brier'], item['ece'],
                        item['log_loss'], item['accuracy'], json.dumps(item['bin_data'])
                    ))

        if verbose:
            print(f"Saved walk-forward results to database for format {fmt_label}.")

        return {
            'player_count': player_count,
            'eval_months': eval_months,
            'aggregated': aggregated_results,
            'monthly': monthly_results
        }
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run walk-forward out-of-sample calibration benchmark.")
    parser.add_argument('--format', type=int, default=0, help="Format player count (0=All, 2=2p, 3=3p, 4=4p)")
    parser.add_argument('--all-formats', action='store_true', help="Run across all formats (0, 2, 3, 4)")
    parser.add_argument('--start-month', type=str, default='2022-01', help="Starting month for out-of-sample evaluation (default: 2022-01)")
    args = parser.parse_args()

    if args.all_formats:
        for fmt in [0, 2, 3, 4]:
            run_walk_forward_evaluation(player_count=fmt, start_eval_month=args.start_month)
    else:
        run_walk_forward_evaluation(player_count=args.format, start_eval_month=args.start_month)
