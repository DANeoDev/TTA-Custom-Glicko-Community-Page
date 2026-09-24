import sys; sys.path.insert(0, '.')
from collections import defaultdict
from src.data.db import get_connection
from src.models.glicko2.calculator import Rating, CALIBRATED_TAU
from src.models.glicko2.adaptive_t import update_rating_adaptive, calibrated_expectation

conn = get_connection()
rows = conn.execute('''
    SELECT match_id, date, tournament, player_a, player_b, outcome_a, weight, player_count
    FROM pairwise_matches
    WHERE glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

PHI = 1.61803398875
GOLDEN_MP_WEIGHTS = {
    2: 1.0,
    3: PHI / 2.0,
    4: (PHI ** 2) / 3.0
}

# Run Pass 1 with exact 15-game prior discovery
ratings_p1 = {}
games_played_p1 = defaultdict(set)
calibrated_priors = {}

months = defaultdict(list)
for r in rows:
    months[r['date'][:7]].append(r)

for m_key in sorted(months.keys()):
    month_matches = months[m_key]
    
    # Check players crossing 15 within this month
    # We can group encounters
    encounters = defaultdict(list)
    for m in month_matches:
        pa, pb = m['player_a'], m['player_b']
        if pa not in ratings_p1: ratings_p1[pa] = Rating(1500.0, 350.0, 0.06)
        if pb not in ratings_p1: ratings_p1[pb] = Rating(1500.0, 350.0, 0.06)
        mid = m['match_id']
        pcount = m['player_count']
        w = GOLDEN_MP_WEIGHTS.get(pcount, 1.0)
        
        # Track matches before/after threshold
        encounters[pa].append((ratings_p1[pb], m['outcome_a'], w, pcount, mid))
        encounters[pb].append((ratings_p1[pa], 1.0 - m['outcome_a'], w, pcount, mid))

    for p_name, enc_list in encounters.items():
        # Check if player crosses 15 in this month
        prev_games = len(games_played_p1[p_name])
        # Add new distinct matches
        distinct_new = []
        for opp_r, sc, w, pc, mid in enc_list:
            if mid not in games_played_p1[p_name]:
                games_played_p1[p_name].add(mid)
                distinct_new.append(mid)
        total_games = len(games_played_p1[p_name])
        
        if prev_games < 15 and total_games >= 15 and p_name not in calibrated_priors:
            # Player crosses threshold!
            # Split encounters into <= 15 and > 15
            needed = 15 - prev_games
            mids_up_to_15 = set(distinct_new[:needed])
            enc_up_to_15 = [(r, s, w, c) for r, s, w, c, m in enc_list if m in mids_up_to_15]
            enc_after_15 = [(r, s, w, c) for r, s, w, c, m in enc_list if m not in mids_up_to_15]
            
            # Update to match 15
            r_at_15 = update_rating_adaptive(ratings_p1[p_name], enc_up_to_15, tau=CALIBRATED_TAU)
            calibrated_priors[p_name] = Rating(r_at_15.rating, r_at_15.rd, r_at_15.sigma)
            
            # Update remaining matches in this month
            if enc_after_15:
                ratings_p1[p_name] = update_rating_adaptive(r_at_15, enc_after_15, tau=CALIBRATED_TAU)
            else:
                ratings_p1[p_name] = r_at_15
        else:
            enc_clean = [(r, s, w, c) for r, s, w, c, m in enc_list]
            ratings_p1[p_name] = update_rating_adaptive(ratings_p1[p_name], enc_clean, tau=CALIBRATED_TAU)

print('Exact prior for Tianren at game 15:', calibrated_priors.get('tianren4561367'))
