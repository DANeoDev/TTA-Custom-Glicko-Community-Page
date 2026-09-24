import sys; sys.path.insert(0, '.')
from collections import defaultdict
from src.data.db import get_connection
from src.models.glicko2.calculator import Rating, CALIBRATED_TAU
from src.models.glicko2.adaptive_t import update_rating_adaptive

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

# Pass 1: Capture exact priors at game 15
ratings_p1 = {}
games_played_p1 = defaultdict(set)
calibrated_priors = {}

months = defaultdict(list)
for r in rows:
    months[r['date'][:7]].append(r)

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
            enc_up_to_15 = [(r, s, w, c) for r, s, w, c, m in enc_list if m in mids_up_to_15]
            enc_after_15 = [(r, s, w, c) for r, s, w, c, m in enc_list if m not in mids_up_to_15]
            
            r_at_15 = update_rating_adaptive(ratings_p1[p_name], enc_up_to_15, tau=CALIBRATED_TAU)
            calibrated_priors[p_name] = Rating(r_at_15.rating, r_at_15.rd, r_at_15.sigma)
            if enc_after_15:
                ratings_p1[p_name] = update_rating_adaptive(r_at_15, enc_after_15, tau=CALIBRATED_TAU)
            else:
                ratings_p1[p_name] = r_at_15
        else:
            enc_clean = [(r, s, w, c) for r, s, w, c, m in enc_list]
            ratings_p1[p_name] = update_rating_adaptive(ratings_p1[p_name], enc_clean, tau=CALIBRATED_TAU)

# Pass 2: Surgical split
ratings_p2 = {}
for p, pr in calibrated_priors.items():
    ratings_p2[p] = Rating(pr.rating, pr.rd, pr.sigma)

def get_r2(p):
    if p not in ratings_p2: ratings_p2[p] = Rating(1500.0, 350.0, 0.06)
    return ratings_p2[p]

games_played_p2 = defaultdict(set)

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
            # Player never reaches 15 games
            enc_clean = [(r, s, w, c) for r, s, w, c, m in enc_list]
            ratings_p2[p_name] = update_rating_adaptive(ratings_p2[p_name], enc_clean, tau=CALIBRATED_TAU)
        elif total_games <= 15:
            # Entirely within frozen window
            pass
        elif prev_games < 15 and total_games > 15:
            # Transition month! Matches up to 15 frozen; only matches after 15 update
            needed = 15 - prev_games
            mids_up_to_15 = set(distinct_new[:needed])
            enc_after_15 = [(r, s, w, c) for r, s, w, c, m in enc_list if m not in mids_up_to_15]
            if enc_after_15:
                ratings_p2[p_name] = update_rating_adaptive(ratings_p2[p_name], enc_after_15, tau=CALIBRATED_TAU)
        else:
            # Fully post-15 games
            enc_clean = [(r, s, w, c) for r, s, w, c, m in enc_list]
            ratings_p2[p_name] = update_rating_adaptive(ratings_p2[p_name], enc_clean, tau=CALIBRATED_TAU)

print('Tianren final rating under Surgical Split:', ratings_p2.get('tianren4561367'))
