import sys; sys.path.insert(0, '.')
import json
from src.data.db import get_connection

conn = get_connection()
rows = conn.execute('''
    SELECT model_type, bin_data_json, brier_score, ece, log_loss, accuracy
    FROM standard_calibration
    WHERE player_count = 0 AND model_type IN ('glicko2_adapt_softer', 'glicko2_adapt_softer_retro', 'glicko2_adapt', 'glicko2_adapt_retro')
    ORDER BY model_type
''').fetchall()

for r in rows:
    mt = r['model_type']
    br = r['brier_score']
    ec = r['ece'] * 100
    acc = r['accuracy']
    print(f'=== {mt} (Brier={br:.4f}, ECE={ec:.2f}%, Acc={acc:.1f}%) ===')
    d = json.loads(r['bin_data_json'])
    labels = d['labels']
    actuals = d['actuals']
    preds = d['preds']
    counts = d['counts']
    print('Bin        | Pred (Soll)  | Obs (Ist)   | Delta (Ist - Soll)   | Matches')
    print('-'*70)
    for lbl, pr, act, cnt in zip(labels, preds, actuals, counts):
        if pr is not None and act is not None:
            delta = act - pr
            print(f'{lbl:10} | {pr*100:6.2f}%      | {act*100:6.2f}%      | {delta*100:+6.2f}%              | {cnt}')
        else:
            print(f'{lbl:10} | N/A          | N/A          | N/A                  | {cnt}')
    print()
