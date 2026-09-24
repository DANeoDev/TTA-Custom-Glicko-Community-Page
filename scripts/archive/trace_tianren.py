import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.db import get_connection
from src.models.glicko2.calculator import Rating, update_rating, CALIBRATED_TAU
from src.models.glicko2.adaptive_t import update_rating_adaptive

conn = get_connection()
rows = conn.execute('''
    SELECT match_id, date, tournament, player_a, player_b, outcome_a, weight, player_count
    FROM pairwise_matches
    WHERE glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

# Let's run Pass 1 and capture tianren's exact rating at game 15
from collections import defaultdict
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
        games_played_p1[pa].add(mid)
        games_played_p1[pb].add(mid)
        encounters[pa].append((ratings_p1[pb], m['outcome_a'], m['weight'], m['player_count']))
        encounters[pb].append((ratings_p1[pa], 1.0 - m['outcome_a'], m['weight'], m['player_count']))
    
    for p, enc in encounters.items():
        ratings_p1[p] = update_rating_adaptive(ratings_p1[p], enc, tau=CALIBRATED_TAU)
        if len(games_played_p1[p]) >= 15 and p not in calibrated_priors:
            calibrated_priors[p] = Rating(ratings_p1[p].rating, ratings_p1[p].rd, ratings_p1[p].sigma)
            if 'tianren' in p.lower():
                print(f'Pass 1 Prior captured for {p} in {m_key}: Rating={ratings_p1[p].rating:.2f}, RD={ratings_p1[p].rd:.2f}, Games={len(games_played_p1[p])}')

print('Tianren prior:', calibrated_priors.get('tianren4561367'))
