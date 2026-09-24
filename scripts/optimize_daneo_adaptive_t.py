import sys; sys.path.insert(0, '.')
import math
from collections import defaultdict
import numpy as np
from src.data.db import get_connection
from src.models.glicko2.calculator import Rating, CALIBRATED_TAU
from src.models.glicko2.engine import g, E
from src.models.glicko2.calculator import update_rating

PHI = 1.61803398875
GOLDEN_MP_WEIGHTS = {
    2: 1.0,
    3: PHI / 2.0,
    4: (PHI ** 2) / 3.0
}

conn = get_connection()
rows = conn.execute('''
    SELECT match_id, date, tournament, player_a, player_b, outcome_a, weight, player_count
    FROM pairwise_matches
    WHERE glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

months = defaultdict(list)
for r in rows:
    months[r['date'][:7]].append(r)

# Pass 1: exact priors
ratings_p1 = {}
games_played_p1 = defaultdict(set)
calibrated_priors = {}

for m_key in sorted(months.keys()):
    month_matches = months[m_key]
    encounters = defaultdict(list)
    for m in month_matches:
        pa, pb = m['player_a'], m['player_b']
        if pa not in ratings_p1: ratings_p1[pa] = Rating(1500.0, 350.0, 0.06)
        if pb not in ratings_p1: ratings_p1[pb] = Rating(1500.0, 350.0, 0.06)
        mid = m['match_id']
        pcount = m['player_count']
        w = GOLDEN_MP_WEIGHTS.get(pcount, 1.0)
        encounters[pa].append((ratings_p1[pb], m['outcome_a'], w, pcount, mid))
        encounters[pb].append((ratings_p1[pa], 1.0 - m['outcome_a'], w, pcount, mid))

    for p_name, enc_list in encounters.items():
        prev_games = len(games_played_p1[p_name])
        distinct_new = []
        for opp_r, sc, w, pc, mid in enc_list:
            if mid not in games_played_p1[p_name]:
                games_played_p1[p_name].add(mid)
                distinct_new.append(mid)
        total_games = len(games_played_p1[p_name])
        
        if prev_games < 15 and total_games >= 15 and p_name not in calibrated_priors:
            needed = 15 - prev_games
            mids_up_to_15 = set(distinct_new[:needed])
            enc_up_to_15 = [(r, s, w) for r, s, w, c, m in enc_list if m in mids_up_to_15]
            enc_after_15 = [(r, s, w) for r, s, w, c, m in enc_list if m not in mids_up_to_15]
            
            r_at_15 = update_rating(ratings_p1[p_name], enc_up_to_15, tau=CALIBRATED_TAU, weighted=True)
            calibrated_priors[p_name] = Rating(r_at_15.rating, r_at_15.rd, r_at_15.sigma)
            if enc_after_15:
                ratings_p1[p_name] = update_rating(r_at_15, enc_after_15, tau=CALIBRATED_TAU, weighted=True)
            else:
                ratings_p1[p_name] = r_at_15
        else:
            enc_clean = [(r, s, w) for r, s, w, c, m in enc_list]
            ratings_p1[p_name] = update_rating(ratings_p1[p_name], enc_clean, tau=CALIBRATED_TAU, weighted=True)

# Pass 2: Surgical split with match predictions recorded
ratings_p2 = {}
for p, pr in calibrated_priors.items():
    ratings_p2[p] = Rating(pr.rating, pr.rd, pr.sigma)

def get_r2(p):
    if p not in ratings_p2: ratings_p2[p] = Rating(1500.0, 350.0, 0.06)
    return ratings_p2[p]

games_played_p2 = defaultdict(set)
eval_data = []

for m_key in sorted(months.keys()):
    month_matches = months[m_key]
    encounters = defaultdict(list)
    for m in month_matches:
        pa, pb = m['player_a'], m['player_b']
        ra = get_r2(pa)
        rb = get_r2(pb)
        mid = m['match_id']
        pcount = m['player_count']
        w = GOLDEN_MP_WEIGHTS.get(pcount, 1.0)
        
        g_val = g(rb.phi)
        x_base = g_val * (ra.mu - rb.mu)
        eval_data.append((pcount, x_base, m['outcome_a']))
        
        encounters[pa].append((rb, m['outcome_a'], w, pcount, mid))
        encounters[pb].append((ra, 1.0 - m['outcome_a'], w, pcount, mid))

    for p_name, enc_list in encounters.items():
        prev_games = len(games_played_p2[p_name])
        distinct_new = []
        for opp_r, sc, w, pc, mid in enc_list:
            if mid not in games_played_p2[p_name]:
                games_played_p2[p_name].add(mid)
                distinct_new.append(mid)
        total_games = len(games_played_p2[p_name])

        if p_name not in calibrated_priors:
            enc_clean = [(r, s, w) for r, s, w, c, m in enc_list]
            ratings_p2[p_name] = update_rating(ratings_p2[p_name], enc_clean, tau=CALIBRATED_TAU, weighted=True)
        elif total_games <= 15:
            pass
        elif prev_games < 15 and total_games > 15:
            needed = 15 - prev_games
            mids_up_to_15 = set(distinct_new[:needed])
            enc_after_15 = [(r, s, w) for r, s, w, c, m in enc_list if m not in mids_up_to_15]
            if enc_after_15:
                ratings_p2[p_name] = update_rating(ratings_p2[p_name], enc_after_15, tau=CALIBRATED_TAU, weighted=True)
        else:
            enc_clean = [(r, s, w) for r, s, w, c, m in enc_list]
            ratings_p2[p_name] = update_rating(ratings_p2[p_name], enc_clean, tau=CALIBRATED_TAU, weighted=True)

print(f'Total pairwise evaluations captured: {len(eval_data)}')

def evaluate_params(params, subset_data):
    alpha, gamma = params
    bin_preds = defaultdict(list)
    bin_actuals = defaultdict(list)
    
    brier_sum = 0.0
    for pcount, x, outcome in subset_data:
        e_base = 1.0 / (1.0 + math.exp(-abs(x)))
        dev = 2.0 * (e_base - 0.5)
        temp = 1.0 + alpha * (dev ** gamma) if alpha > 0 else 1.0
        
        p_a = 1.0 / (1.0 + math.exp(-x / temp))
        p_fav = max(p_a, 1.0 - p_a)
        fav_outcome = outcome if p_a >= 0.5 else (1.0 - outcome)
        
        brier_sum += (p_a - outcome) ** 2
        
        b_idx = min(9, int((p_fav - 0.5) / 0.05))
        bin_preds[b_idx].append(p_fav)
        bin_actuals[b_idx].append(fav_outcome)
        
    n_total = len(subset_data)
    brier = brier_sum / n_total
    
    x_means = []
    y_means = []
    weights = []
    ece = 0.0
    for i in range(10):
        if bin_preds[i]:
            xp = float(np.mean(bin_preds[i]))
            yp = float(np.mean(bin_actuals[i]))
            cnt = len(bin_preds[i])
            x_means.append(xp)
            y_means.append(yp)
            weights.append(cnt)
            ece += (cnt / n_total) * abs(yp - xp)
            
    x_arr = np.array(x_means)
    y_arr = np.array(y_means)
    w_arr = np.array(weights)
    
    xc = x_arr - 0.5
    yc = y_arr - 0.5
    m = float(np.sum(w_arr * xc * yc) / max(1e-9, np.sum(w_arr * xc * xc)))
    
    loss = abs(m - 1.0) + 0.1 * ece
    return loss, m, ece, brier

formats = [0, 2, 3, 4]
results = {}

for fmt in formats:
    if fmt == 0:
        sub = eval_data
    else:
        sub = [d for d in eval_data if d[0] == fmt]
        
    print(f'\n--- Optimizing for Format {fmt} (Matches: {len(sub)}) ---')
    l0, m0, ece0, br0 = evaluate_params([0.0, 1.0], sub)
    print(f'  Baseline (alpha=0): Slope={m0:.4f}, ECE={ece0*100:.2f}%, Brier={br0:.4f}')
    
    best_loss = 999.0
    best_p = (0.0, 1.0)
    best_stats = (m0, ece0, br0)
    
    for a in [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15]:
        for g_val in [0.7, 0.8, 0.9, 1.0, 1.2]:
            l_val, m_val, e_val, b_val = evaluate_params([a, g_val], sub)
            if l_val < best_loss:
                best_loss = l_val
                best_p = (round(a, 4), round(g_val, 2))
                best_stats = (m_val, e_val, b_val)
                
    print(f'  Optimal: alpha={best_p[0]}, gamma={best_p[1]} => Slope={best_stats[0]:.4f}, ECE={best_stats[1]*100:.2f}%, Brier={best_stats[2]:.4f}')
    results[fmt] = (best_p[0], best_p[1], best_stats[0], best_stats[1], best_stats[2])

print('\n======================================================')
print('FINAL OPTIMAL ADAPTIVE-T PARAMETERS (DANeo Gold Standard):')
print('======================================================')
for fmt, (a, g_val, m, ec, br) in results.items():
    fmt_lbl = f'{fmt}P' if fmt > 0 else 'All'
    print(f'  Format {fmt_lbl} ({fmt}): alpha={a}, gamma={g_val} | Slope={m:.4f} | ECE={ec*100:.2f}% | Brier={br:.4f}')
