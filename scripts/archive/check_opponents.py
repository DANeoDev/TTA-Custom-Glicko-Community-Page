import sys; sys.path.insert(0, '.')
from src.data.db import get_connection

conn = get_connection()
matches = conn.execute('''
    SELECT match_id, date, player_a, player_b, outcome_a
    FROM pairwise_matches
    WHERE (player_a LIKE '%tianren%' OR player_b LIKE '%tianren%') AND glicko_eligible = 1
    ORDER BY date, pairwise_id
''').fetchall()

opponents = set()
for m in matches:
    opp = m['player_b'] if 'tianren' in m['player_a'].lower() else m['player_a']
    opponents.add(opp)

print(f'Tianren played against {len(opponents)} unique opponents across {len(matches)} pairwise matches.')

# Check rating deltas for these opponents in normal vs retro
opp_deltas = []
for opp in opponents:
    r_norm = conn.execute('SELECT rating, rd FROM player_ratings WHERE player_name = ? AND model_type = \"glicko2_adapt_softer\" AND player_count = 0', (opp,)).fetchone()
    r_retro = conn.execute('SELECT rating, rd FROM player_ratings WHERE player_name = ? AND model_type = \"glicko2_adapt_softer_retro\" AND player_count = 0', (opp,)).fetchone()
    if r_norm and r_retro:
        opp_deltas.append((opp, r_norm[0], r_retro[0], r_retro[0] - r_norm[0]))

opp_deltas.sort(key=lambda x: x[3], reverse=True)
print('Top 5 opponents with biggest positive delta (Retro - Normal):')
for o, rn, rr, d in opp_deltas[:5]:
    print(f'  {o}: Normal={rn:.1f} -> Retro={rr:.1f} (Delta={d:+.1f})')
print('Top 5 opponents with biggest negative delta (Retro - Normal):')
for o, rn, rr, d in opp_deltas[-5:]:
    print(f'  {o}: Normal={rn:.1f} -> Retro={rr:.1f} (Delta={d:+.1f})')
avg_opp_delta = sum(d for _, _, _, d in opp_deltas) / len(opp_deltas)
print(f'Average opponent delta: {avg_opp_delta:+.2f}')
