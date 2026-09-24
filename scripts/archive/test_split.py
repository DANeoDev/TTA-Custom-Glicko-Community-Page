import sys; sys.path.insert(0, '.')
from collections import defaultdict
from src.data.db import get_connection

conn = get_connection()
rows = conn.execute('''
    SELECT match_id, date, tournament, player_a, player_b, outcome_a, weight, player_count
    FROM pairwise_matches
    WHERE glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

tianren_matches = [r for r in rows if 'tianren' in r['player_a'].lower() or 'tianren' in r['player_b'].lower()]
dec_matches = [m for m in tianren_matches if m['date'].startswith('2025-12')]
jan_matches = [m for m in tianren_matches if m['date'].startswith('2026-01')]

dec_seen = set()
dec_distinct = []
for m in dec_matches:
    if m['match_id'] not in dec_seen:
        dec_seen.add(m['match_id'])
        dec_distinct.append(m)

jan_seen = set()
jan_distinct = []
for m in jan_matches:
    if m['match_id'] not in jan_seen:
        jan_seen.add(m['match_id'])
        jan_distinct.append(m)

print('Tianren Dec distinct matches:', len(dec_distinct))
print('Tianren Jan distinct matches:', len(jan_distinct))
for idx, m in enumerate(jan_distinct, 1):
    d = m['date']
    mid = m['match_id']
    print('  Jan match', idx, '(Career match', 11+idx, '): date=', d, 'id=', mid)
