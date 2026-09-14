import json
import math
from collections import defaultdict
import numpy as np
from flask import Blueprint, render_template, session, request
from src.data.db import get_connection

analysis_bp = Blueprint('analysis', __name__)

VALID_MODELS = {
    'glicko2_std': 'Glicko-2 Standard',
    'glicko2_mp': 'Glicko-2 MP-Weighted',
    'whr': 'Whole-History Rating'
}

VALID_FORMATS = {
    0: 'All Formats',
    2: '2-Player (Duel)',
    3: '3-Player',
    4: '4-Player'
}

VALID_RESET_MODES = {
    'continuous': {
        'name': 'Continuous',
        'desc': 'Unbroken multi-year Bayesian career trajectory across all historical games.'
    },
    'soft': {
        'name': 'Soft Reset',
        'desc': 'Annual Golden Ratio soft reset with uncertainty expansion and deflationary tier stabilization.'
    },
    'amplified': {
        'name': 'Hard Reset',
        'desc': 'Annual hard season reset with amplified uncertainty expansion and tier realignment.'
    }
}

def compute_spearman_corr(ranks1, ranks2):
    n = len(ranks1)
    if n < 2:
        return 1.0
    d_sq_sum = sum((r1 - r2) ** 2 for r1, r2 in zip(ranks1, ranks2))
    return 1.0 - (6.0 * d_sq_sum) / (n * (n * n - 1))

def compute_calibration(conn, player_count=0, sample_size=15000, model_keys=None):
    """Computes calibration curves and Brier scores across models and reset variations."""
    if model_keys is None:
        model_keys = [
            'glicko2_std', 'glicko2_mp', 'whr',
            'glicko2_std_soft', 'glicko2_mp_soft', 'whr_soft',
            'glicko2_std_amplified', 'glicko2_mp_amplified', 'whr_amplified'
        ]

    ratings = {}
    for m in model_keys:
        rows = conn.execute(
            'SELECT player_name, rating FROM player_ratings WHERE model_type = ? AND player_count = ?',
            (m, player_count)
        ).fetchall()
        ratings[m] = {r['player_name']: r['rating'] for r in rows}

    if player_count > 0:
        matches = conn.execute(
            'SELECT player_a, player_b, outcome_a FROM pairwise_matches WHERE player_count = ? ORDER BY match_id DESC LIMIT ?',
            (player_count, sample_size)
        ).fetchall()
    else:
        matches = conn.execute(
            'SELECT player_a, player_b, outcome_a FROM pairwise_matches ORDER BY match_id DESC LIMIT ?',
            (sample_size,)
        ).fetchall()

    bin_labels = ['50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
    ideal_points = [0.55, 0.65, 0.75, 0.85, 0.95]

    calib_data = {
        'labels': bin_labels,
        'ideal': ideal_points,
        'models': {}
    }

    bin_edges = np.linspace(0.5, 1.0, 6)
    num_bins = len(bin_labels)

    for m in model_keys:
        m_ratings = ratings.get(m, {})
        preds = []
        actuals = []
        for match in matches:
            pa, pb, out = match['player_a'], match['player_b'], match['outcome_a']
            if pa in m_ratings and pb in m_ratings:
                ra, rb = m_ratings[pa], m_ratings[pb]
                p = 1.0 / (1.0 + 10.0 ** (-(ra - rb) / 400.0))
                # Fold to favored player perspective (p >= 0.50) to eliminate mirror redundancy
                if p >= 0.5:
                    preds.append(p)
                    actuals.append(out)
                else:
                    preds.append(1.0 - p)
                    actuals.append(1.0 - out)

        if not preds:
            calib_data['models'][m] = {'brier': 0.25, 'actuals': ideal_points, 'counts': [0]*num_bins, 'preds': ideal_points}
            continue

        preds_arr = np.array(preds)
        actuals_arr = np.array(actuals)
        brier = float(np.mean((preds_arr - actuals_arr) ** 2))

        bin_actuals = []
        bin_preds = []
        bin_counts = []
        for i in range(num_bins):
            low, high = bin_edges[i], bin_edges[i+1]
            mask = (preds_arr >= low) & (preds_arr < high if i < num_bins - 1 else preds_arr <= high)
            cnt = int(np.sum(mask))
            bin_counts.append(cnt)
            if cnt > 0:
                bin_actuals.append(round(float(np.mean(actuals_arr[mask])), 3))
                bin_preds.append(round(float(np.mean(preds_arr[mask])), 3))
            else:
                bin_actuals.append(round((low + high) / 2, 2))
                bin_preds.append(round((low + high) / 2, 2))

        # Expected Calibration Error (ECE)
        total_n = len(preds_arr)
        ece = 0.0
        if total_n > 0:
            for i in range(num_bins):
                cnt = bin_counts[i]
                if cnt > 0:
                    ece += (cnt / total_n) * abs(bin_actuals[i] - bin_preds[i])

        calib_data['models'][m] = {
            'brier': round(brier, 4),
            'ece': round(ece, 4),
            'ece_pct': round(ece * 100.0, 2),
            'actuals': bin_actuals,
            'preds': bin_preds,
            'counts': bin_counts
        }

    return calib_data

@analysis_bp.route('/analysis')
def index():
    model_param = request.args.get('model')
    if model_param in VALID_MODELS:
        session['active_model'] = model_param
    active_model = session.get('active_model', 'glicko2_std')

    format_param = request.args.get('format')
    if format_param is not None:
        try:
            fmt_int = int(format_param)
            if fmt_int in VALID_FORMATS:
                session['active_format'] = fmt_int
        except ValueError:
            pass
    active_format = session.get('active_format', 0)

    reset_param = request.args.get('reset_mode')
    if reset_param in VALID_RESET_MODES:
        session['active_reset_mode'] = reset_param
    active_reset_mode = session.get('active_reset_mode', 'continuous')
    if active_reset_mode not in VALID_RESET_MODES:
        active_reset_mode = 'continuous'

    if active_reset_mode == 'soft':
        key_map = {'glicko2_std': 'glicko2_std_soft', 'glicko2_mp': 'glicko2_mp_soft', 'whr': 'whr_soft'}
    elif active_reset_mode == 'amplified':
        key_map = {'glicko2_std': 'glicko2_std_amplified', 'glicko2_mp': 'glicko2_mp_amplified', 'whr': 'whr_amplified'}
    else:
        key_map = {'glicko2_std': 'glicko2_std', 'glicko2_mp': 'glicko2_mp', 'whr': 'whr'}

    conn = get_connection()
    try:
        # 1. Summary Statistics per model for active_format and active_reset_mode
        models_stats = {}
        for m_key in ['glicko2_std', 'glicko2_mp', 'whr']:
            target_key = key_map[m_key]
            rows = conn.execute(
                'SELECT rating, rd, c_rating FROM player_ratings WHERE model_type = ? AND player_count = ?',
                (target_key, active_format)
            ).fetchall()

            if rows:
                ratings = np.array([r['rating'] for r in rows])
                rds = np.array([r['rd'] for r in rows])
                c_ratings = np.array([r['c_rating'] for r in rows])
                models_stats[m_key] = {
                    'count': len(ratings),
                    'mean_rating': round(float(np.mean(ratings)), 1),
                    'median_rating': round(float(np.median(ratings)), 1),
                    'std_rating': round(float(np.std(ratings)), 1),
                    'min_rating': round(float(np.min(ratings)), 1),
                    'max_rating': round(float(np.max(ratings)), 1),
                    'mean_rd': round(float(np.mean(rds)), 1),
                    'mean_c_rating': round(float(np.mean(c_ratings)), 1),
                }

        # 2. Cross-Model Correlation Matrix for active_reset_mode (players with >= 15 games in active_format)
        corr_rows = conn.execute(
            'SELECT '
            'p.name, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rating END) as r_std, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rank END) as rank_std, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rating END) as r_mp, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rank END) as rank_mp, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rating END) as r_whr, '
            'MAX(CASE WHEN pr.model_type = ? THEN pr.rank END) as rank_whr, '
            'MAX(pr.opponents_count) as opps '
            'FROM players p '
            'JOIN player_ratings pr ON p.name = pr.player_name AND pr.player_count = ? '
            'GROUP BY p.name '
            'HAVING r_std IS NOT NULL AND r_mp IS NOT NULL AND r_whr IS NOT NULL AND opps >= 15',
            (key_map['glicko2_std'], key_map['glicko2_std'],
             key_map['glicko2_mp'], key_map['glicko2_mp'],
             key_map['whr'], key_map['whr'], active_format)
        ).fetchall()

        r_std = [r['r_std'] for r in corr_rows]
        r_mp = [r['r_mp'] for r in corr_rows]
        r_whr = [r['r_whr'] for r in corr_rows]

        rank_std = [r['rank_std'] for r in corr_rows]
        rank_mp = [r['rank_mp'] for r in corr_rows]
        rank_whr = [r['rank_whr'] for r in corr_rows]

        correlations = {
            'pearson_std_mp': round(float(np.corrcoef(r_std, r_mp)[0, 1]), 4) if len(r_std) > 1 else 1.0,
            'pearson_std_whr': round(float(np.corrcoef(r_std, r_whr)[0, 1]), 4) if len(r_std) > 1 else 1.0,
            'pearson_mp_whr': round(float(np.corrcoef(r_mp, r_whr)[0, 1]), 4) if len(r_std) > 1 else 1.0,
            'spearman_std_mp': round(compute_spearman_corr(rank_std, rank_mp), 4),
            'spearman_std_whr': round(compute_spearman_corr(rank_std, rank_whr), 4),
            'spearman_mp_whr': round(compute_spearman_corr(rank_mp, rank_whr), 4),
            'sample_size': len(corr_rows)
        }

        # 2b. Comprehensive 9x9 Cross-Engine Agreement Matrix (3 Models x 3 Reset Modes)
        ALL_9_ENGINES = [
            ('glicko2_std', 'G2 Std (Career)', 'G2 Std Cont'),
            ('glicko2_std_soft', 'G2 Std (Soft Reset)', 'G2 Std Soft'),
            ('glicko2_std_amplified', 'G2 Std (Hard Reset)', 'G2 Std Hard'),
            ('glicko2_mp', 'G2 MP (Career)', 'G2 MP Cont'),
            ('glicko2_mp_soft', 'G2 MP (Soft Reset)', 'G2 MP Soft'),
            ('glicko2_mp_amplified', 'G2 MP (Hard Reset)', 'G2 MP Hard'),
            ('whr', 'WHR (Career)', 'WHR Cont'),
            ('whr_soft', 'WHR (Soft Reset)', 'WHR Soft'),
            ('whr_amplified', 'WHR (Hard Reset)', 'WHR Hard'),
        ]

        engine_keys = [e[0] for e in ALL_9_ENGINES]
        placeholders = ', '.join(['?'] * len(engine_keys))
        
        # Query all ratings and ranks for eligible players (opps >= 15)
        raw_9_rows = conn.execute(f'''
            SELECT player_name, model_type, rating, rank
            FROM player_ratings
            WHERE player_count = ? AND opponents_count >= 15 AND model_type IN ({placeholders})
        ''', [active_format] + engine_keys).fetchall()

        player_engine_ratings = defaultdict(dict)
        player_engine_ranks = defaultdict(dict)
        for r in raw_9_rows:
            p = r['player_name']
            m = r['model_type']
            player_engine_ratings[p][m] = r['rating']
            player_engine_ranks[p][m] = r['rank']

        # Filter players that have ratings across all 9 engines
        eligible_players = [p for p, d in player_engine_ratings.items() if len(d) == len(engine_keys)]
        matrix_sample_size = len(eligible_players)

        matrix_9x9_pearson = []
        matrix_9x9_spearman = []

        for i, (k_i, name_i, short_i) in enumerate(ALL_9_ENGINES):
            row_p = []
            row_s = []
            vals_i = [player_engine_ratings[p][k_i] for p in eligible_players]
            rnk_i = [player_engine_ranks[p][k_i] for p in eligible_players]
            for j, (k_j, name_j, short_j) in enumerate(ALL_9_ENGINES):
                if i == j:
                    row_p.append(1.0)
                    row_s.append(1.0)
                else:
                    vals_j = [player_engine_ratings[p][k_j] for p in eligible_players]
                    rnk_j = [player_engine_ranks[p][k_j] for p in eligible_players]
                    if matrix_sample_size > 1:
                        p_corr = float(np.corrcoef(vals_i, vals_j)[0, 1])
                        s_corr = compute_spearman_corr(rnk_i, rnk_j)
                    else:
                        p_corr = 1.0
                        s_corr = 1.0
                    row_p.append(round(p_corr, 4))
                    row_s.append(round(s_corr, 4))
            matrix_9x9_pearson.append(row_p)
            matrix_9x9_spearman.append(row_s)

        matrix_9x9_data = {
            'engines': [{'key': e[0], 'name': e[1], 'short': e[2]} for e in ALL_9_ENGINES],
            'pearson': matrix_9x9_pearson,
            'spearman': matrix_9x9_spearman,
            'sample_size': matrix_sample_size
        }

        # 3. Rating Distribution Histograms (for chart in active reset mode)
        bins = list(range(1000, 2400, 100))
        bin_labels = [f'{b}-{b+99}' for b in bins[:-1]]
        
        std_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', (key_map['glicko2_std'], active_format)).fetchall()]
        mp_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', (key_map['glicko2_mp'], active_format)).fetchall()]
        whr_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', (key_map['whr'], active_format)).fetchall()]

        std_counts, _ = np.histogram(std_rows, bins=bins) if std_rows else ([], [])
        mp_counts, _ = np.histogram(mp_rows, bins=bins) if mp_rows else ([], [])
        whr_counts, _ = np.histogram(whr_rows, bins=bins) if whr_rows else ([], [])

        hist_data = {
            'labels': bin_labels,
            'std': [int(x) for x in std_counts],
            'mp': [int(x) for x in mp_counts],
            'whr': [int(x) for x in whr_counts],
        }

        # 4. Calibration Curves (calculating all 9 models)
        calib_data = compute_calibration(conn, player_count=active_format, sample_size=12000)

        # 5. Title Rating Benchmark & Skill Tier Distribution in active reset mode
        title_defs = [
            ('GM', 'Grandmaster (GM)', 'badge-gm'),
            ('M', 'Master (M)', 'badge-m'),
            ('P', 'Platinum (P)', 'badge-p'),
            ('G', 'Gold (G)', 'badge-g'),
            (None, 'Untitled / Challenger', 'badge-rank')
        ]
        title_benchmarks = []
        for code, label, badge_cls in title_defs:
            if code:
                t_sql = '''
                    SELECT pr.rating as r_std, pr_mp.rating as r_mp, pr_whr.rating as r_whr, pr.c_rating, pr.win_rate, pr.opponents_count
                    FROM players p
                    JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = ? AND pr.player_count = ?
                    LEFT JOIN player_ratings pr_mp ON p.name = pr_mp.player_name AND pr_mp.model_type = ? AND pr_mp.player_count = ?
                    LEFT JOIN player_ratings pr_whr ON p.name = pr_whr.player_name AND pr_whr.model_type = ? AND pr_whr.player_count = ?
                    WHERE p.title = ? AND pr.opponents_count >= 15
                '''
                t_rows = conn.execute(t_sql, (key_map['glicko2_std'], active_format, key_map['glicko2_mp'], active_format, key_map['whr'], active_format, code)).fetchall()
            else:
                t_sql = '''
                    SELECT pr.rating as r_std, pr_mp.rating as r_mp, pr_whr.rating as r_whr, pr.c_rating, pr.win_rate, pr.opponents_count
                    FROM players p
                    JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = ? AND pr.player_count = ?
                    LEFT JOIN player_ratings pr_mp ON p.name = pr_mp.player_name AND pr_mp.model_type = ? AND pr_mp.player_count = ?
                    LEFT JOIN player_ratings pr_whr ON p.name = pr_whr.player_name AND pr_whr.model_type = ? AND pr_whr.player_count = ?
                    WHERE (p.title IS NULL OR p.title = "") AND pr.opponents_count >= 15
                '''
                t_rows = conn.execute(t_sql, (key_map['glicko2_std'], active_format, key_map['glicko2_mp'], active_format, key_map['whr'], active_format)).fetchall()

            if t_rows:
                r_std_list = [r['r_std'] for r in t_rows if r['r_std'] is not None]
                r_mp_list = [r['r_mp'] for r in t_rows if r['r_mp'] is not None]
                r_whr_list = [r['r_whr'] for r in t_rows if r['r_whr'] is not None]
                c_list = [r['c_rating'] for r in t_rows if r['c_rating'] is not None]
                wr_list = [r['win_rate'] for r in t_rows if r['win_rate'] is not None]

                title_benchmarks.append({
                    'code': code or 'NONE',
                    'label': label,
                    'badge_cls': badge_cls,
                    'count': len(t_rows),
                    'mean_std': round(float(np.mean(r_std_list)), 1) if r_std_list else 1500.0,
                    'mean_mp': round(float(np.mean(r_mp_list)), 1) if r_mp_list else 1500.0,
                    'mean_whr': round(float(np.mean(r_whr_list)), 1) if r_whr_list else 1500.0,
                    'median_c': round(float(np.median(c_list)), 1) if c_list else 450.0,
                    'mean_win_rate': round(float(np.mean(wr_list)), 1) if wr_list else 0.0
                })

        return render_template(
            'analysis.html',
            stats=models_stats,
            correlations=correlations,
            hist_json=json.dumps(hist_data),
            calib_json=json.dumps(calib_data),
            calib_data=calib_data,
            title_benchmarks=title_benchmarks,
            matrix_9x9=matrix_9x9_data,
            active_model=active_model,
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
            active_reset_mode=active_reset_mode,
            reset_mode=active_reset_mode,
            reset_modes=VALID_RESET_MODES,
            key_map=key_map
        )
    finally:
        conn.close()

@analysis_bp.route('/analysis/calibration')
def calibration():
    format_param = request.args.get('format')
    active_format = 0
    if format_param is not None:
        try:
            active_format = int(format_param)
        except ValueError:
            active_format = 0

    reset_param = request.args.get('reset_mode')
    active_reset_mode = reset_param if reset_param in VALID_RESET_MODES else 'continuous'

    eval_param = request.args.get('eval_mode', 'walk_forward')
    active_eval_mode = eval_param if eval_param in ['walk_forward', 'retrospective'] else 'walk_forward'

    conn = get_connection()
    try:
        calib_data = compute_calibration(conn, player_count=active_format, sample_size=20000)

        # Query Walk-Forward Calibration Metrics
        wf_rows = conn.execute("""
            SELECT model_type, period_month, matches_evaluated, brier_score, ece, log_loss, accuracy, bin_data_json
            FROM walk_forward_calibration
            WHERE player_count = ?
            ORDER BY period_month
        """, (active_format,)).fetchall()

        wf_data = {
            'has_data': len(wf_rows) > 0,
            'models': {},
            'timeline': [],
            'monthly_brier': {'glicko2_std': [], 'glicko2_mp': [], 'whr': []}
        }

        months_set = set()
        month_model_brier = defaultdict(dict)

        for r in wf_rows:
            m = r['model_type']
            period = r['period_month']
            if period == 'AGGREGATED':
                bin_info = json.loads(r['bin_data_json']) if r['bin_data_json'] else {}
                wf_data['models'][m] = {
                    'matches': r['matches_evaluated'],
                    'brier': r['brier_score'],
                    'ece': r['ece'],
                    'ece_pct': round(r['ece'] * 100.0, 2),
                    'log_loss': r['log_loss'],
                    'accuracy': r['accuracy'],
                    'actuals': bin_info.get('actuals', []),
                    'preds': bin_info.get('preds', []),
                    'counts': bin_info.get('counts', []),
                    'labels': bin_info.get('labels', [])
                }
            else:
                months_set.add(period)
                month_model_brier[period][m] = r['brier_score']

        sorted_eval_months = sorted(months_set)
        wf_data['timeline'] = sorted_eval_months
        for m_key in ['glicko2_std', 'glicko2_mp', 'whr']:
            wf_data['monthly_brier'][m_key] = [
                month_model_brier[mo].get(m_key, None) for mo in sorted_eval_months
            ]

        return render_template(
            'analysis_calibration.html',
            calib_data=calib_data,
            calib_json=json.dumps(calib_data),
            wf_data=wf_data,
            wf_json=json.dumps(wf_data),
            active_eval_mode=active_eval_mode,
            eval_mode=active_eval_mode,
            active_format=active_format,
            formats=VALID_FORMATS,
            models=VALID_MODELS,
            active_reset_mode=active_reset_mode,
            reset_modes=VALID_RESET_MODES
        )
    finally:
        conn.close()

@analysis_bp.route('/analysis/movers')
def movers():
    format_param = request.args.get('format')
    active_format = 0
    if format_param is not None:
        try:
            active_format = int(format_param)
        except ValueError:
            active_format = 0

    comparison = request.args.get('compare', 'std_vs_mp')
    min_games = int(request.args.get('min_games', 15))

    conn = get_connection()
    try:
        if comparison == 'std_vs_whr':
            m1, m2 = 'glicko2_std', 'whr'
            label1, label2 = 'Glicko-2 Standard', 'Whole-History Rating'
        elif comparison == 'mp_vs_whr':
            m1, m2 = 'glicko2_mp', 'whr'
            label1, label2 = 'Glicko-2 MP-Weighted', 'Whole-History Rating'
        else:
            m1, m2 = 'glicko2_std', 'glicko2_mp'
            label1, label2 = 'Glicko-2 Standard', 'Glicko-2 MP-Weighted'

        # Top Climbers (gained most ranks under m2 vs m1: rank1 - rank2 > 0)
        climbers = conn.execute(
            'SELECT p.name, p.country_code, p.title, '
            'pr1.rank as rank1, pr2.rank as rank2, '
            '(pr1.rank - pr2.rank) as rank_diff, '
            'pr1.rating as rating1, pr2.rating as rating2, '
            'pr1.c_rating as c_rating1, pr2.c_rating as c_rating2, '
            'pr1.opponents_count as opps, pr1.win_rate '
            'FROM players p '
            'JOIN player_ratings pr1 ON p.name = pr1.player_name AND pr1.model_type = ? AND pr1.player_count = ? '
            'JOIN player_ratings pr2 ON p.name = pr2.player_name AND pr2.model_type = ? AND pr2.player_count = ? '
            'WHERE pr1.opponents_count >= ? '
            'ORDER BY (pr1.rank - pr2.rank) DESC LIMIT 25',
            (m1, active_format, m2, active_format, min_games)
        ).fetchall()

        # Top Fallers (lost most ranks under m2 vs m1: rank1 - rank2 < 0)
        fallers = conn.execute(
            'SELECT p.name, p.country_code, p.title, '
            'pr1.rank as rank1, pr2.rank as rank2, '
            '(pr1.rank - pr2.rank) as rank_diff, '
            'pr1.rating as rating1, pr2.rating as rating2, '
            'pr1.c_rating as c_rating1, pr2.c_rating as c_rating2, '
            'pr1.opponents_count as opps, pr1.win_rate '
            'FROM players p '
            'JOIN player_ratings pr1 ON p.name = pr1.player_name AND pr1.model_type = ? AND pr1.player_count = ? '
            'JOIN player_ratings pr2 ON p.name = pr2.player_name AND pr2.model_type = ? AND pr2.player_count = ? '
            'WHERE pr1.opponents_count >= ? '
            'ORDER BY (pr1.rank - pr2.rank) ASC LIMIT 25',
            (m1, active_format, m2, active_format, min_games)
        ).fetchall()

        return render_template(
            'analysis_movers.html',
            climbers=climbers,
            fallers=fallers,
            comparison=comparison,
            label1=label1,
            label2=label2,
            min_games=min_games,
            active_format=active_format,
            formats=VALID_FORMATS
        )
    finally:
        conn.close()

@analysis_bp.route('/analysis/activity')
def activity():
    conn = get_connection()
    try:
        # Active vs Inactive counts
        active_count = conn.execute("SELECT count(*) FROM players WHERE last_played > '2025-05-31'").fetchone()[0]
        inactive_count = conn.execute("SELECT count(*) FROM players WHERE last_played IS NULL OR last_played <= '2025-05-31'").fetchone()[0]
        total_players = active_count + inactive_count

        # Match counts by format
        fmt_counts = conn.execute("SELECT player_count, count(*) as count FROM matches GROUP BY player_count ORDER BY player_count").fetchall()
        match_stats = {r['player_count']: r['count'] for r in fmt_counts}

        # Country representation (top 15) with 4 average rating columns by title status
        country_rows = conn.execute(
            "SELECT p.country_code, "
            "COUNT(DISTINCT p.name) as total_count, "
            "ROUND(AVG(CASE WHEN p.title = 'GM' THEN pr.rating END), 1) as avg_gm, "
            "ROUND(AVG(CASE WHEN p.title IN ('GM', 'M') THEN pr.rating END), 1) as avg_m_plus, "
            "ROUND(AVG(CASE WHEN p.title IN ('GM', 'M', 'P') THEN pr.rating END), 1) as avg_p_plus, "
            "ROUND(AVG(pr.rating), 1) as avg_all "
            "FROM players p "
            "JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = 'glicko2_std' AND pr.player_count = 0 "
            "WHERE p.country_code IS NOT NULL "
            "GROUP BY p.country_code "
            "ORDER BY total_count DESC LIMIT 15"
        ).fetchall()

        # Title distribution
        title_rows = conn.execute(
            "SELECT title, count(*) as count FROM players WHERE title IS NOT NULL GROUP BY title ORDER BY count DESC"
        ).fetchall()

        return render_template(
            'analysis_activity.html',
            active_count=active_count,
            inactive_count=inactive_count,
            total_players=total_players,
            match_stats=match_stats,
            countries=country_rows,
            titles=title_rows,
            formats=VALID_FORMATS
        )
    finally:
        conn.close()
