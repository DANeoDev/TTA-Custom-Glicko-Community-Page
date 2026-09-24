import sys
sys.path.insert(0, '.')
import json
from src.data.db import get_connection

conn = get_connection()
rows = conn.execute('''
    SELECT model_type, bin_data_json, brier_score, ece, log_loss, accuracy
    FROM standard_calibration
    WHERE player_count = 0 AND model_type IN ('glicko2_adapt_softer', 'glicko2_adapt_softer_retro', 'glicko2_adapt', 'glicko2_adapt_retro')
''').fetchall()

for r in rows:
    mt = r['model_type']
    br = r['brier_score']
    ec = r['ece'] * 100
    acc = r['accuracy']
    print('=== ' + mt + ' (Brier=' + str(round(br, 4)) + ', ECE=' + str(round(ec, 2)) + '%, Acc=' + str(round(acc, 1)) + '%) ===')
    bins = json.loads(r['bin_data_json'])
    print('Bin        | Pred (Soll)  | Obs (Ist)   | Delta      | Matches')
    print('-'*60)
    for b in bins:
        p_soll = b.get('pred_mean', b.get('expected', 0.0))
        p_ist = b.get('actual_mean', b.get('actual', 0.0))
        delta = p_ist - p_soll
        cnt = b.get('count', 0)
        lbl = b.get('bin_label', b.get('range', ''))
        print(f'{lbl:10} | {p_soll*100:6.2f}%      | {p_ist*100:6.2f}%      | {delta*100:+6.2f}%   | {cnt}')
    print()
