import sys; sys.path.insert(0, '.')
import json
from src.data.db import get_connection

conn = get_connection()
row = conn.execute('''
    SELECT model_type, bin_data_json, brier_score, ece, log_loss, accuracy
    FROM standard_calibration
    WHERE player_count = 0 AND model_type = 'glicko2_std_retro'
''').fetchone()

mt = row['model_type']
br = row['brier_score']
ec = row['ece'] * 100
acc = row['accuracy']
print(f'=== {mt} (Brier={br:.4f}, ECE={ec:.2f}%, Acc={acc:.1f}%) ===')
d = json.loads(row['bin_data_json'])
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
