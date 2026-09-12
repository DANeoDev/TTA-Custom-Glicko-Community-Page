import json
import math
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

def compute_spearman_corr(ranks1, ranks2):
    n = len(ranks1)
    if n < 2:
        return 1.0
    d_sq_sum = sum((r1 - r2) ** 2 for r1, r2 in zip(ranks1, ranks2))
    return 1.0 - (6.0 * d_sq_sum) / (n * (n * n - 1))

def compute_calibration(conn, player_count=0, sample_size=15000):
    """Computes calibration curves and Brier scores for all three models."""
    ratings = {}
    for m in ['glicko2_std', 'glicko2_mp', 'whr']:
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

    bin_labels = ['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
    ideal_points = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]

    calib_data = {
        'labels': bin_labels,
        'ideal': ideal_points,
        'models': {}
    }

    bin_edges = np.linspace(0.0, 1.0, 11)

    for m in ['glicko2_std', 'glicko2_mp', 'whr']:
        m_ratings = ratings.get(m, {})
        preds = []
        actuals = []
        for match in matches:
            pa, pb, out = match['player_a'], match['player_b'], match['outcome_a']
            if pa in m_ratings and pb in m_ratings:
                ra, rb = m_ratings[pa], m_ratings[pb]
                p = 1.0 / (1.0 + 10.0 ** (-(ra - rb) / 400.0))
                # Symmetrize encounters (A vs B and B vs A)
                preds.append(p)
                actuals.append(out)
                preds.append(1.0 - p)
                actuals.append(1.0 - out)

        if not preds:
            calib_data['models'][m] = {'brier': 0.25, 'actuals': ideal_points, 'counts': [0]*10, 'preds': ideal_points}
            continue

        preds_arr = np.array(preds)
        actuals_arr = np.array(actuals)
        brier = float(np.mean((preds_arr - actuals_arr) ** 2))

        bin_actuals = []
        bin_preds = []
        bin_counts = []
        for i in range(10):
            low, high = bin_edges[i], bin_edges[i+1]
            mask = (preds_arr >= low) & (preds_arr < high if i < 9 else preds_arr <= high)
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
            for i in range(10):
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

    conn = get_connection()
    try:
        # 1. Summary Statistics per model for active_format
        models_stats = {}
        for m_key in ['glicko2_std', 'glicko2_mp', 'whr']:
            rows = conn.execute(
                'SELECT rating, rd, c_rating FROM player_ratings WHERE model_type = ? AND player_count = ?',
                (m_key, active_format)
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

        # 2. Cross-Model Correlation Matrix (players with >= 15 games in active_format)
        corr_rows = conn.execute(
            'SELECT '
            'p.name, '
            'MAX(CASE WHEN pr.model_type = "glicko2_std" THEN pr.rating END) as r_std, '
            'MAX(CASE WHEN pr.model_type = "glicko2_std" THEN pr.rank END) as rank_std, '
            'MAX(CASE WHEN pr.model_type = "glicko2_mp" THEN pr.rating END) as r_mp, '
            'MAX(CASE WHEN pr.model_type = "glicko2_mp" THEN pr.rank END) as rank_mp, '
            'MAX(CASE WHEN pr.model_type = "whr" THEN pr.rating END) as r_whr, '
            'MAX(CASE WHEN pr.model_type = "whr" THEN pr.rank END) as rank_whr, '
            'MAX(pr.opponents_count) as opps '
            'FROM players p '
            'JOIN player_ratings pr ON p.name = pr.player_name AND pr.player_count = ? '
            'GROUP BY p.name '
            'HAVING r_std IS NOT NULL AND r_mp IS NOT NULL AND r_whr IS NOT NULL AND opps >= 15',
            (active_format,)
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

        # 3. Rating Distribution Histograms (for chart)
        bins = list(range(1000, 2400, 100))
        bin_labels = [f'{b}-{b+99}' for b in bins[:-1]]
        
        std_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type="glicko2_std" AND player_count = ?', (active_format,)).fetchall()]
        mp_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type="glicko2_mp" AND player_count = ?', (active_format,)).fetchall()]
        whr_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type="whr" AND player_count = ?', (active_format,)).fetchall()]

        std_counts, _ = np.histogram(std_rows, bins=bins) if std_rows else ([], [])
        mp_counts, _ = np.histogram(mp_rows, bins=bins) if mp_rows else ([], [])
        whr_counts, _ = np.histogram(whr_rows, bins=bins) if whr_rows else ([], [])

        hist_data = {
            'labels': bin_labels,
            'std': [int(x) for x in std_counts],
            'mp': [int(x) for x in mp_counts],
            'whr': [int(x) for x in whr_counts],
        }

        # 4. Calibration Curve
        calib_data = compute_calibration(conn, player_count=active_format, sample_size=12000)

        # 5. Title Rating Benchmark & Skill Tier Distribution
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
                    JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = "glicko2_std" AND pr.player_count = ?
                    LEFT JOIN player_ratings pr_mp ON p.name = pr_mp.player_name AND pr_mp.model_type = "glicko2_mp" AND pr_mp.player_count = ?
                    LEFT JOIN player_ratings pr_whr ON p.name = pr_whr.player_name AND pr_whr.model_type = "whr" AND pr_whr.player_count = ?
                    WHERE p.title = ? AND pr.opponents_count >= 15
                '''
                t_rows = conn.execute(t_sql, (active_format, active_format, active_format, code)).fetchall()
            else:
                t_sql = '''
                    SELECT pr.rating as r_std, pr_mp.rating as r_mp, pr_whr.rating as r_whr, pr.c_rating, pr.win_rate, pr.opponents_count
                    FROM players p
                    JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = "glicko2_std" AND pr.player_count = ?
                    LEFT JOIN player_ratings pr_mp ON p.name = pr_mp.player_name AND pr_mp.model_type = "glicko2_mp" AND pr_mp.player_count = ?
                    LEFT JOIN player_ratings pr_whr ON p.name = pr_whr.player_name AND pr_whr.model_type = "whr" AND pr_whr.player_count = ?
                    WHERE (p.title IS NULL OR p.title = "") AND pr.opponents_count >= 15
                '''
                t_rows = conn.execute(t_sql, (active_format, active_format, active_format)).fetchall()

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
            active_model=active_model,
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS
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

    conn = get_connection()
    try:
        calib_data = compute_calibration(conn, player_count=active_format, sample_size=20000)
        return render_template(
            'analysis_calibration.html',
            calib_data=calib_data,
            calib_json=json.dumps(calib_data),
            active_format=active_format,
            formats=VALID_FORMATS,
            models=VALID_MODELS
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
