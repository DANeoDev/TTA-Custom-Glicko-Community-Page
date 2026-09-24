import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.db import get_connection
conn = get_connection()

matches = conn.execute('''
    SELECT match_id, date, tournament, player_a, player_b, outcome_a, weight, player_count
    FROM pairwise_matches
    WHERE (player_a LIKE '%Tianren%' OR player_b LIKE '%Tianren%') AND glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

seen = set()
dm = []
for m in matches:
    if m['match_id'] not in seen:
        seen.add(m['match_id'])
        dm.append(m)

print(f'Distinct matches for Tianren: {len(dm)}')
for i, m in enumerate(dm[:25], 1):
    opp = m['player_b'] if 'Tianren' in m['player_a'] else m['player_a']
    score = m['outcome_a'] if 'Tianren' in m['player_a'] else 1.0 - m['outcome_a']
    d = m['date']
    t = m['tournament']
    print(f'{i:2d}. {d} | vs {opp} (score={score}) | {t}')
