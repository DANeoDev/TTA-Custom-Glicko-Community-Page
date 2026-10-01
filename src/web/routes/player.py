from datetime import datetime
import json
import math
from typing import Dict, Optional, Any
from flask import Blueprint, render_template, abort, request, session
from src.data.db import get_connection
from src.web.routes.leaderboard import VALID_MODELS, VALID_FORMATS, VALID_RESET_MODES
from src.models.glicko2.engine import Rating, update_rating
from src.models.glicko2.adaptive_t import update_rating_adaptive, ADAPTIVE_T_PARAMS
from src.models.glicko2.calculator import GOLDEN_MP_WEIGHTS
from src.data.badges import classify_division_tier, TIER_TITLE_MAP, TIER_NAMES, TITLE_ORDER, HISTORICAL_WC_INFO, TITLE_FULL_NAMES

player_bp = Blueprint('player', __name__)

TIER_BONUS = {'WC': 150, 'SGM': 100, 'GM': 60, 'M': 40, 'P': 25, 'G': 15, 'S': 5, 'B': 0, 'W': -5}

def get_player_yearly_titles(conn, player_name: str) -> Dict[int, Dict[str, Any]]:
    """Retrieves the highest tournament division title and display info held by a player in each calendar year."""
    yearly = {}
    tier_map = {1: 'GM', 2: 'M', 3: 'P', 4: 'G', 5: 'S', 6: 'B', 7: 'W'}

    # 1. Matches table
    tourney_rows = conn.execute("""
        SELECT tournament, date
        FROM matches
        WHERE (player1 = ? OR player2 = ? OR player3 = ? OR player4 = ?)
          AND tournament IS NOT NULL
    """, (player_name, player_name, player_name, player_name)).fetchall()

    for tr in tourney_rows:
        d = tr['date']
        if d and len(d) >= 4 and d[:4].isdigit():
            yr = int(d[:4])
            t = classify_division_tier(tr['tournament'])
            if t is not None:
                code = tier_map.get(t, 'W')
                if yr not in yearly or TITLE_ORDER.get(code, 99) < TITLE_ORDER.get(yearly[yr]['title'], 99):
                    yearly[yr] = {'title': code, 'title_name': TITLE_FULL_NAMES.get(code, code), 'tier': t}

    # 2. Tournament_records table
    rec_rows = conn.execute("""
        SELECT tournament_name, division, finish_date, placement, medal
        FROM tournament_records
        WHERE player_name = ? AND is_career_total = 0
    """, (player_name,)).fetchall()

    for r in rec_rows:
        fd = r['finish_date']
        if fd and len(fd) >= 4 and fd[:4].isdigit():
            yr = int(fd[:4])
            t_name = r['tournament_name'] or ''
            div = r['division'] or ''
            plac = str(r['placement'] or '')
            med = (r['medal'] or '').lower()
            is_win = plac.startswith('1 /') or plac == '1' or med == 'gold'

            if t_name in ('International Championship', 'Intermezzo Championship', 'Royal League') and div in ('Grandmaster', 'Diamond', 'Emperor') and is_win:
                yearly[yr] = {'title': 'SGM', 'title_name': 'Super GM', 'tier': 1}
            elif yr not in yearly:
                t = classify_division_tier(f"{t_name} {div}")
                if t is not None:
                    code = tier_map.get(t, 'W')
                    yearly[yr] = {'title': code, 'title_name': TITLE_FULL_NAMES.get(code, code), 'tier': t}

    # 3. Known World Champions
    for p_wc, (wc_yr, wc_title) in HISTORICAL_WC_INFO.items():
        if p_wc.lower() == player_name.lower():
            yearly[wc_yr] = {'title': 'WC', 'title_name': 'World Champion', 'tier': 0}

    # 4. Check players table peak_title and peak_year
    p_row = conn.execute('SELECT peak_title, peak_year FROM players WHERE name = ? COLLATE NOCASE', (player_name,)).fetchone()
    if p_row and p_row['peak_title'] and p_row['peak_year']:
        pk_yr = p_row['peak_year']
        pk_code = p_row['peak_title']
        if pk_yr not in yearly or TITLE_ORDER.get(pk_code, 99) < TITLE_ORDER.get(yearly[pk_yr]['title'], 99):
            t_val = 0 if pk_code == 'WC' else (1 if pk_code == 'SGM' else next((k for k, v in tier_map.items() if v == pk_code), 7))
            yearly[pk_yr] = {
                'title': pk_code,
                'title_name': TITLE_FULL_NAMES.get(pk_code, pk_code),
                'tier': t_val
            }

    return yearly

def get_player_yearly_tiers(conn, player_name: str) -> Dict[int, int]:
    """Retrieves the highest tournament division tier played by a player in each calendar year (0=WC, 1=GM/SGM, etc.)."""
    y_titles = get_player_yearly_titles(conn, player_name)
    return {yr: info.get('tier', 7) for yr, info in y_titles.items()}

KNOWN_PLAYER_ALIASES = {
    'tinaren': 'tianren4561367',
    'tianren': 'tianren4561367',
}

@player_bp.route('/player/<player_name>')
def profile(player_name):
    # Handle model switch
    model_param = request.args.get('model')
    if model_param in VALID_MODELS:
        session['active_model'] = model_param
    active_model = session.get('active_model')
    if not active_model or active_model not in VALID_MODELS:
        active_model = 'glicko2_daneo'
        session['active_model'] = 'glicko2_daneo'

    # Handle format switch
    format_param = request.args.get('format')
    if format_param is not None:
        try:
            fmt_int = int(format_param)
            if fmt_int in (0, 2, 3, 4):
                session['active_format'] = fmt_int
        except ValueError:
            pass
    active_format = session.get('active_format', 0)

    # Handle reset_mode switch (continuous, softer)
    reset_param = request.args.get('reset_mode')
    if reset_param in ('soft', 'amplified'):
        reset_param = 'softer'
    if reset_param in VALID_RESET_MODES:
        session['active_reset_mode'] = reset_param
    active_reset_mode = session.get('active_reset_mode', 'continuous')
    if active_reset_mode not in VALID_RESET_MODES:
        active_reset_mode = 'continuous'

    conn = get_connection()
    try:
        lookup_name = KNOWN_PLAYER_ALIASES.get(player_name.lower(), player_name)
        player_row = conn.execute(
            'SELECT name, country_code, title, title_count, badge_reason, last_played, peak_title, peak_year FROM players WHERE name = ? COLLATE NOCASE',
            (lookup_name,)
        ).fetchone()

        if not player_row:
            # Try to see if player exists in matches
            exists = conn.execute(
                'SELECT player1 FROM matches WHERE LOWER(player1)=LOWER(?) OR LOWER(player2)=LOWER(?) OR LOWER(player3)=LOWER(?) OR LOWER(player4)=LOWER(?) LIMIT 1',
                (lookup_name, lookup_name, lookup_name, lookup_name)
            ).fetchone()
            if not exists:
                abort(404)
            player = {'name': lookup_name, 'country_code': None, 'title': None, 'title_count': 0, 'last_played': None, 'first_played': None, 'peak_title': None, 'peak_year': None}
        else:
            player = dict(player_row)

        pk_t = player.get('peak_title')
        cr_t = player.get('title')
        player['is_peak_higher'] = bool(pk_t and player.get('peak_year') and (not cr_t or TITLE_ORDER.get(pk_t, 99) < TITLE_ORDER.get(cr_t, 99)))

        # Query first played match date for debut display
        first_m = conn.execute(
            'SELECT MIN(date) as first_played FROM matches WHERE player1=? OR player2=? OR player3=? OR player4=?',
            (player['name'], player['name'], player['name'], player['name'])
        ).fetchone()
        player['first_played'] = first_m['first_played'] if first_m and first_m['first_played'] else None

        player_name = player['name']

        # Determine target model keys according to active reset mode
        if active_reset_mode == 'soft':
            key_map = {'glicko2_std': 'glicko2_std_soft', 'glicko2_mp': 'glicko2_mp_soft', 'glicko2_adapt': 'glicko2_adapt_soft', 'whr': 'whr_soft', 'glicko2_daneo': 'glicko2_daneo_soft'}
        elif active_reset_mode == 'softer':
            key_map = {'glicko2_std': 'glicko2_std_softer', 'glicko2_mp': 'glicko2_mp_softer', 'glicko2_adapt': 'glicko2_adapt_softer', 'whr': 'whr_softer', 'glicko2_daneo': 'glicko2_daneo_softer'}
        elif active_reset_mode == 'amplified':
            key_map = {'glicko2_std': 'glicko2_std_amplified', 'glicko2_mp': 'glicko2_mp_amplified', 'glicko2_adapt': 'glicko2_adapt_amplified', 'whr': 'whr_amplified', 'glicko2_daneo': 'glicko2_daneo_soft'}
        else:
            key_map = {'glicko2_std': 'glicko2_std', 'glicko2_mp': 'glicko2_mp', 'glicko2_adapt': 'glicko2_adapt', 'whr': 'whr', 'glicko2_daneo': 'glicko2_daneo'}

        inv_map = {v: k for k, v in key_map.items()}
        target_keys = list(key_map.values())
        placeholders = ', '.join(['?'] * len(target_keys))

        # Fetch ratings for target model keys in this format
        ratings_rows = conn.execute(
            f'SELECT model_type, rating, rd, sigma, c_rating, rank, rank_delta, opponents_count, wins, losses, draws, win_rate '
            f'FROM player_ratings WHERE player_name = ? AND player_count = ? AND model_type IN ({placeholders})',
            [player_name, active_format] + target_keys
        ).fetchall()

        ratings_by_model = {inv_map.get(r['model_type'], r['model_type']): dict(r) for r in ratings_rows}

        # Fetch GlickoD ratings across all player counts (0, 2, 3, 4) for the active reset mode
        glickod_target_key = key_map.get('glicko2_daneo', 'glicko2_daneo')
        glickod_rows = conn.execute(
            'SELECT player_count, rating, rd, sigma, c_rating, rank, rank_delta, opponents_count, wins, losses, draws, win_rate '
            'FROM player_ratings WHERE player_name = ? AND model_type = ? AND player_count IN (0, 2, 3, 4)',
            [player_name, glickod_target_key]
        ).fetchall()
        glickod_by_format = {r['player_count']: dict(r) for r in glickod_rows}

        # Fetch history points for Chart.js across both continuous and season reset modes
        chart_base_keys = ['glicko2_daneo', 'glicko2_std', 'glicko2_mp', 'glicko2_adapt', 'whr']
        chart_reset_keys = [f"{k}_softer" for k in chart_base_keys]
        all_chart_query_keys = chart_base_keys + chart_reset_keys
        ph_chart = ', '.join(['?'] * len(all_chart_query_keys))

        hist_rows = conn.execute(
            f'SELECT model_type, period_date, rating, rd, c_rating '
            f'FROM rating_history WHERE player_name = ? AND player_count = ? AND model_type IN ({ph_chart}) ORDER BY period_date ASC',
            [player_name, active_format] + all_chart_query_keys
        ).fetchall()

        # Build unified chart data supporting both Continuous and Season Reset, and Expected vs Conservative
        dates_set = set()
        series_cont = {m: {} for m in chart_base_keys}
        series_cont_c = {m: {} for m in chart_base_keys}
        series_reset = {m: {} for m in chart_base_keys}
        series_reset_c = {m: {} for m in chart_base_keys}

        for r in hist_rows:
            d = r['period_date']
            m = r['model_type']
            dates_set.add(d)
            if m in chart_base_keys:
                series_cont[m][d] = round(r['rating'], 1)
                series_cont_c[m][d] = round(r['c_rating'], 1) if r['c_rating'] is not None else round(r['rating'] - 2.0 * r['rd'], 1)
            elif m.endswith('_softer'):
                bm = m.replace('_softer', '')
                if bm in chart_base_keys:
                    series_reset[bm][d] = round(r['rating'], 1)
                    series_reset_c[bm][d] = round(r['c_rating'], 1) if r['c_rating'] is not None else round(r['rating'] - 2.0 * r['rd'], 1)

        sorted_dates = sorted(list(dates_set))
        model_series = series_cont
        model_series_c = series_cont_c
        chart_data = {
            'labels': sorted_dates,
            'continuous': {
                'expected': {m: [series_cont[m].get(d) for d in sorted_dates] for m in chart_base_keys},
                'conservative': {m: [series_cont_c[m].get(d) for d in sorted_dates] for m in chart_base_keys}
            },
            'softer': {
                'expected': {m: [series_reset[m].get(d) for d in sorted_dates] for m in chart_base_keys},
                'conservative': {m: [series_reset_c[m].get(d) for d in sorted_dates] for m in chart_base_keys}
            },
            # Flat backwards-compatible keys for continuous expected and conservative:
            'glicko2_std': [series_cont['glicko2_std'].get(d) for d in sorted_dates],
            'glicko2_mp': [series_cont['glicko2_mp'].get(d) for d in sorted_dates],
            'glicko2_adapt': [series_cont['glicko2_adapt'].get(d) for d in sorted_dates],
            'whr': [series_cont['whr'].get(d) for d in sorted_dates],
            'glicko2_daneo': [series_cont['glicko2_daneo'].get(d) for d in sorted_dates],
            'glicko2_std_c': [series_cont_c['glicko2_std'].get(d) for d in sorted_dates],
            'glicko2_mp_c': [series_cont_c['glicko2_mp'].get(d) for d in sorted_dates],
            'glicko2_adapt_c': [series_cont_c['glicko2_adapt'].get(d) for d in sorted_dates],
            'whr_c': [series_cont_c['whr'].get(d) for d in sorted_dates],
            'glicko2_daneo_c': [series_cont_c['glicko2_daneo'].get(d) for d in sorted_dates]
        }

        # Build Season Reset comparison chart data for player profile (Continuous vs Season Reset vs Soft Reset)
        reset_models = ['glicko2_daneo', 'glicko2_std', 'glicko2_mp', 'glicko2_adapt', 'whr']
        reset_target_keys = []
        for rm in reset_models:
            reset_target_keys.extend([rm, f"{rm}_softer", f"{rm}_soft"])
        ph_reset = ', '.join(['?'] * len(reset_target_keys))
        reset_hist_rows = conn.execute(
            f'SELECT model_type, period_date, rating '
            f'FROM rating_history WHERE player_name = ? AND player_count = ? AND model_type IN ({ph_reset}) '
            f'ORDER BY period_date ASC',
            [player_name, active_format] + reset_target_keys
        ).fetchall()

        reset_dates_set = set()
        reset_model_series = {rm: {'continuous': {}, 'softer': {}, 'soft': {}} for rm in reset_models}
        for hr in reset_hist_rows:
            d = hr['period_date']
            m = hr['model_type']
            reset_dates_set.add(d)
            for rm in reset_models:
                if m == rm:
                    reset_model_series[rm]['continuous'][d] = round(hr['rating'], 1)
                elif m == f"{rm}_softer":
                    reset_model_series[rm]['softer'][d] = round(hr['rating'], 1)
                elif m == f"{rm}_soft":
                    reset_model_series[rm]['soft'][d] = round(hr['rating'], 1)

        sorted_reset_dates = sorted(list(reset_dates_set))
        reset_chart_data = {
            'labels': sorted_reset_dates,
            'active_model': active_model,
        }
        for rm in reset_models:
            reset_chart_data[rm] = {
                'continuous': [reset_model_series[rm]['continuous'].get(d) for d in sorted_reset_dates],
                'softer': [reset_model_series[rm]['softer'].get(d) for d in sorted_reset_dates],
                'soft': [reset_model_series[rm]['soft'].get(d) for d in sorted_reset_dates],
            }

        # Calculate Career Peak Year evaluation from yearly_player_stats
        yearly_stats_rows = conn.execute(
            'SELECT year, opponents_count, wins, losses, draws, win_rate '
            'FROM yearly_player_stats '
            'WHERE player_name = ? AND player_count = ? AND opponents_count > 0 '
            'ORDER BY year ASC',
            (player_name, active_format)
        ).fetchall()

        # If format has no matches (e.g. 4P for 2P/3P specialists), fall back to overall player_count = 0
        if not yearly_stats_rows and active_format != 0:
            yearly_stats_rows = conn.execute(
                'SELECT year, opponents_count, wins, losses, draws, win_rate '
                'FROM yearly_player_stats '
                'WHERE player_name = ? AND player_count = 0 AND opponents_count > 0 '
                'ORDER BY year ASC',
                (player_name,)
            ).fetchall()

        career_years = []
        career_peak_year = None
        best_score = -999999.0

        peaks_by_year = {}
        peak_rows = conn.execute(
            'SELECT substr(period_date, 1, 4) as yr, MAX(rating) as max_r '
            'FROM rating_history WHERE player_name = ? AND player_count = ? '
            'GROUP BY yr',
            (player_name, active_format if active_format in (2, 3, 4) else 0)
        ).fetchall()
        for pr in peak_rows:
            try:
                peaks_by_year[int(pr['yr'])] = round(pr['max_r'], 1) if pr['max_r'] else None
            except (ValueError, TypeError):
                pass

        yearly_titles = get_player_yearly_titles(conn, player_name)
        p_peak_yr = player.get('peak_year')

        for yr_row in yearly_stats_rows:
            y_val = yr_row['year']
            peak_r = peaks_by_year.get(y_val)

            w = yr_row['wins']
            wr = yr_row['win_rate']
            opps = yr_row['opponents_count']

            t_info = yearly_titles.get(y_val, {})
            y_title = t_info.get('title')
            y_title_name = t_info.get('title_name')

            bonus = TIER_BONUS.get(y_title, 0)
            if p_peak_yr and y_val == p_peak_yr:
                bonus += 30

            score = (w * 1.5) + (wr * 2.0) + ((peak_r - 1500) * 0.4 if peak_r else 0) + bonus

            y_entry = {
                'year': y_val,
                'opps': opps,
                'wins': w,
                'losses': yr_row['losses'],
                'draws': yr_row['draws'],
                'win_rate': wr,
                'peak_rating': peak_r,
                'score': round(score, 1),
                'has_wc': y_title == 'WC',
                'title': y_title,
                'title_name': y_title_name
            }
            career_years.append(y_entry)

            if score > best_score:
                best_score = score
                career_peak_year = y_entry

        # Fallback if title is missing on career_peak_year but player has a peak_title
        if career_peak_year and not career_peak_year.get('title') and player.get('peak_title'):
            career_peak_year['title'] = player['peak_title']
            career_peak_year['title_name'] = TITLE_FULL_NAMES.get(player['peak_title'], player['peak_title'])
            if player['peak_title'] == 'WC':
                career_peak_year['has_wc'] = True

        # Match History Pagination & Querying
        try:
            match_page = int(request.args.get('match_page', 1))
            if match_page < 1:
                match_page = 1
        except (ValueError, TypeError):
            match_page = 1

        matches_per_page = 30

        if active_format in (2, 3, 4):
            count_sql = (
                'SELECT COUNT(*) FROM matches '
                'WHERE (player1=? OR player2=? OR player3=? OR player4=?) AND player_count = ?'
            )
            count_params = (player_name, player_name, player_name, player_name, active_format)
            match_sql = (
                'SELECT match_id, tournament, date, player_count, player1, score1, player2, score2, '
                'player3, score3, player4, score4, replay_code '
                'FROM matches '
                'WHERE (player1=? OR player2=? OR player3=? OR player4=?) AND player_count = ? '
                'ORDER BY date DESC, match_id DESC LIMIT ? OFFSET ?'
            )
        else:
            count_sql = (
                'SELECT COUNT(*) FROM matches '
                'WHERE player1=? OR player2=? OR player3=? OR player4=?'
            )
            count_params = (player_name, player_name, player_name, player_name)
            match_sql = (
                'SELECT match_id, tournament, date, player_count, player1, score1, player2, score2, '
                'player3, score3, player4, score4, replay_code '
                'FROM matches '
                'WHERE player1=? OR player2=? OR player3=? OR player4=? '
                'ORDER BY date DESC, match_id DESC LIMIT ? OFFSET ?'
            )

        total_matches_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_match_pages = max(1, math.ceil(total_matches_count / matches_per_page))
        if match_page > total_match_pages and total_match_pages > 0:
            match_page = total_match_pages
        offset = (match_page - 1) * matches_per_page

        if active_format in (2, 3, 4):
            match_params = (player_name, player_name, player_name, player_name, active_format, matches_per_page, offset)
        else:
            match_params = (player_name, player_name, player_name, player_name, matches_per_page, offset)

        match_rows = conn.execute(match_sql, match_params).fetchall()

        # Prior calibration status (provisional if < 15 matches AND active within last year)
        max_date_row = conn.execute("SELECT MAX(date) FROM matches").fetchone()
        db_max_date = max_date_row[0] if max_date_row and max_date_row[0] else '1900-01-01'

        p_last_date = player['last_played'] if player and 'last_played' in player.keys() and player['last_played'] else None
        if not p_last_date:
            player_last_date_row = conn.execute(
                "SELECT MAX(date) FROM matches WHERE player1=? OR player2=? OR player3=? OR player4=?",
                (player_name, player_name, player_name, player_name)
            ).fetchone()
            p_last_date = player_last_date_row[0] if player_last_date_row and player_last_date_row[0] else '1900-01-01'

        try:
            d_max = datetime.strptime(db_max_date[:10], '%Y-%m-%d').date()
            d_last = datetime.strptime(p_last_date[:10], '%Y-%m-%d').date()
            is_inactive_over_1y = (d_max - d_last).days > 365
        except Exception:
            is_inactive_over_1y = False

        is_calibrating = (total_matches_count < 15 and not is_inactive_over_1y)

        # Collect all participant names across the current page of matches
        page_participants = {player_name}
        for m in match_rows:
            for i in range(1, 5):
                p_col = m[f'player{i}']
                if p_col:
                    page_participants.add(p_col)

        # Pre-fetch participant ratings for the active model in one query
        eff_model = active_model if active_model in ('glicko2_daneo', 'glicko2_std', 'glicko2_mp', 'glicko2_adapt') else 'glicko2_daneo'
        if active_reset_mode != 'continuous':
            db_model_key = f"{eff_model}_{active_reset_mode}"
        else:
            db_model_key = eff_model

        ratings_cache = {}
        if page_participants:
            p_list = list(page_participants)
            placeholders = ','.join(['?'] * len(p_list))
            rating_lookup_rows = conn.execute(
                f"SELECT player_name, rating, rd FROM player_ratings WHERE model_type = ? AND player_count = ? AND player_name IN ({placeholders})",
                [db_model_key, active_format] + p_list
            ).fetchall()
            for r_row in rating_lookup_rows:
                ratings_cache[r_row['player_name']] = (r_row['rating'], r_row['rd'])

        recent_matches = []
        for m in match_rows:
            participants = []
            for i in range(1, 5):
                p_col = m[f'player{i}']
                s_col = m[f'score{i}']
                if p_col and s_col is not None:
                    participants.append({'name': p_col, 'score': float(s_col)})

            # Sort participants by score DESC
            participants.sort(key=lambda x: x['score'], reverse=True)
            placement = 1
            for rank_idx, p_item in enumerate(participants, 1):
                if p_item['name'] == player_name:
                    placement = rank_idx
                    break

            # Compute authentic rating delta using active engine / GlickoD
            p_cnt = m['player_count']
            if p_cnt >= 2 and len(participants) >= 2:
                p_info = ratings_cache.get(player_name, (1500.0, 350.0))
                p_obj = Rating(p_info[0], p_info[1], 0.03)

                match_tuples = []
                if eff_model == 'glicko2_daneo':
                    w_N = GOLDEN_MP_WEIGHTS.get(p_cnt, 1.0)
                elif eff_model in ('glicko2_adapt', 'glicko2_mp'):
                    w_N = 1.0 / max(1, p_cnt - 1)
                else:  # glicko2_std
                    w_N = 1.0

                my_score = next((p['score'] for p in participants if p['name'] == player_name), None)
                for p_item in participants:
                    if p_item['name'] == player_name:
                        continue
                    opp_name = p_item['name']
                    opp_score = p_item['score']
                    opp_info = ratings_cache.get(opp_name, (1500.0, 350.0))
                    opp_obj = Rating(opp_info[0], opp_info[1], 0.03)

                    if my_score is not None:
                        if my_score > opp_score:
                            outcome = 1.0
                        elif my_score < opp_score:
                            outcome = 0.0
                        else:
                            outcome = 0.5
                    else:
                        outcome = 1.0 if placement == 1 else 0.0

                    match_tuples.append((opp_obj, outcome, w_N, p_cnt))

                if match_tuples:
                    if eff_model == 'glicko2_adapt':
                        new_r = update_rating_adaptive(p_obj, match_tuples, tau=0.3, params_dict=ADAPTIVE_T_PARAMS)
                    else:
                        enc3 = [(t[0], t[1], t[2]) for t in match_tuples]
                        new_r = update_rating(p_obj, enc3, tau=0.3, weighted=(eff_model in ('glicko2_mp', 'glicko2_daneo')))
                    m_delta = round(new_r.rating - p_obj.rating, 1)
                else:
                    m_delta = 0.0
            else:
                m_delta = None

            recent_matches.append({
                'match_id': m['match_id'],
                'tournament': m['tournament'],
                'date': m['date'],
                'player_count': m['player_count'],
                'placement': placement,
                'participants': participants,
                'replay_code': m['replay_code'] if 'replay_code' in m.keys() else None,
                'rating_delta': m_delta
            })

        # Head-to-Head records against rivals (filtered by format if active_format in 2, 3, 4)
        if active_format in (2, 3, 4):
            h2h_rows = conn.execute(
                'SELECT '
                'CASE WHEN player_a = ? THEN player_b ELSE player_a END as opponent, '
                'COUNT(*) as games, '
                'SUM(CASE WHEN (player_a = ? AND outcome_a = 1.0) OR (player_b = ? AND outcome_a = 0.0) THEN 1 ELSE 0 END) as wins, '
                'SUM(CASE WHEN (player_a = ? AND outcome_a = 0.0) OR (player_b = ? AND outcome_a = 1.0) THEN 1 ELSE 0 END) as losses, '
                'SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws '
                'FROM pairwise_matches '
                'WHERE (player_a = ? OR player_b = ?) AND player_count = ? '
                'GROUP BY opponent '
                'ORDER BY games DESC, wins DESC LIMIT 200',
                (player_name, player_name, player_name, player_name, player_name, player_name, player_name, active_format)
            ).fetchall()
        else:
            h2h_rows = conn.execute(
                'SELECT '
                'CASE WHEN player_a = ? THEN player_b ELSE player_a END as opponent, '
                'COUNT(*) as games, '
                'SUM(CASE WHEN (player_a = ? AND outcome_a = 1.0) OR (player_b = ? AND outcome_a = 0.0) THEN 1 ELSE 0 END) as wins, '
                'SUM(CASE WHEN (player_a = ? AND outcome_a = 0.0) OR (player_b = ? AND outcome_a = 1.0) THEN 1 ELSE 0 END) as losses, '
                'SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws '
                'FROM pairwise_matches '
                'WHERE player_a = ? OR player_b = ? '
                'GROUP BY opponent '
                'ORDER BY games DESC, wins DESC LIMIT 200',
                (player_name, player_name, player_name, player_name, player_name, player_name, player_name)
            ).fetchall()

        h2h_list = []
        for r in h2h_rows:
            g = r['games']
            w = r['wins']
            l = r['losses']
            d = r['draws']
            wr = round((w + 0.5 * d) / max(1, g) * 100.0, 1)
            h2h_list.append({
                'opponent': r['opponent'],
                'games': g,
                'wins': w,
                'losses': l,
                'draws': d,
                'win_rate': wr
            })

        # Career Tournament Achievements
        ach_row = conn.execute(
            'SELECT total_titles, world_titles, international_titles, intermezzo_titles, royal_league_titles, other_titles, '
            'gold_medals, silver_medals, bronze_medals, summary_text, top_achievements_json '
            'FROM player_achievements WHERE player_name = ?',
            (player_name,)
        ).fetchone()

        achievements = dict(ach_row) if ach_row else None
        top_achievements = json.loads(ach_row['top_achievements_json']) if ach_row and ach_row['top_achievements_json'] else []

        # Dynamic narrative insights
        career_summary = achievements['summary_text'] if achievements and achievements.get('summary_text') else None

        narrative = {
            'career_summary': career_summary
        }

        return render_template(
            'player.html',
            player=player,
            ratings=ratings_by_model,
            glickod_by_format=glickod_by_format,
            chart_json=json.dumps(chart_data),
            reset_chart_json=json.dumps(reset_chart_data),
            recent_matches=recent_matches,
            h2h=h2h_list,
            narrative=narrative,
            achievements=achievements,
            top_achievements=top_achievements,
            active_model=active_model,
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
            active_reset_mode=active_reset_mode,
            reset_mode=active_reset_mode,
            reset_modes=VALID_RESET_MODES,
            career_peak_year=career_peak_year,
            career_years=career_years,
            total_matches_count=total_matches_count,
            total_match_pages=total_match_pages,
            match_page=match_page,
            is_calibrating=is_calibrating
        )
    finally:
        conn.close()


@player_bp.route('/player/<player_name>/achievements')
def player_achievements(player_name):
    conn = get_connection()
    try:
        lookup_name = KNOWN_PLAYER_ALIASES.get(player_name.lower(), player_name)
        player_row = conn.execute(
            'SELECT name, country_code, title, title_count, last_played, peak_title, peak_year FROM players WHERE LOWER(name) = LOWER(?)',
            (lookup_name,)
        ).fetchone()
        if not player_row:
            abort(404)
        player = dict(player_row)
        pk_t = player.get('peak_title')
        cr_t = player.get('title')
        player['is_peak_higher'] = bool(pk_t and player.get('peak_year') and (not cr_t or TITLE_ORDER.get(pk_t, 99) < TITLE_ORDER.get(cr_t, 99)))
        player_name = player['name']

        ach_row = conn.execute(
            'SELECT * FROM player_achievements WHERE player_name = ? COLLATE NOCASE',
            (player_name,)
        ).fetchone()

        records_rows = conn.execute(
            'SELECT record_id, tournament_name, season, division, placement, points, medal, details, finish_date, is_career_total '
            'FROM tournament_records WHERE player_name = ? COLLATE NOCASE '
            'ORDER BY finish_date DESC, record_id DESC',
            (player_name,)
        ).fetchall()

        CGE_TOURNAMENT_MAP = {
            'International Championship': 'https://account.czechgames.com/tournaments/detail/21',
            'Intermezzo Championship': 'https://account.czechgames.com/tournaments/detail/19',
            'Royal League': 'https://account.czechgames.com/tournaments/detail/5000',
            'RL_': 'https://account.czechgames.com/tournaments/detail/5000',
            'Sodium Ladder': 'https://account.czechgames.com/tournaments/detail/5169',
            'Mercurial Ladder': 'https://account.czechgames.com/tournaments/detail/4193',
            'Survivors Cup': 'https://account.czechgames.com/tournaments/detail/5731',
            'World Championship': 'https://account.czechgames.com/tournaments/detail/5633',
            'Australian Open': 'https://account.czechgames.com/tournaments/detail/5703',
            'French Open': 'https://account.czechgames.com/tournaments/detail/5860',
            'Wimbledon': 'https://account.czechgames.com/tournaments/detail/4933',
            'Slow Burn': 'https://account.czechgames.com/tournaments/detail/5979',
            'Quick and Dirty': 'https://account.czechgames.com/tournaments/detail/4500',
            'Transcontinental Ladder': 'https://account.czechgames.com/tournaments/detail/53',
            'TCL': 'https://account.czechgames.com/tournaments/detail/53',
            'Leaderboard Trophy': 'https://account.czechgames.com/tournaments/detail/5633',
        }

        def get_cge_url(t_name):
            if not t_name:
                return None
            for k, url in CGE_TOURNAMENT_MAP.items():
                if k.lower() in t_name.lower():
                    return url
            return None

        def get_tournament_category(t_name):
            if not t_name:
                return 'other'
            tl = t_name.lower()
            if 'world championship' in tl or 'worlds' in tl:
                return 'wcs'
            if 'international' in tl or 'intermezzo' in tl or 'royal league' in tl or tl.startswith('rl_'):
                return 'major'
            if 'ladder' in tl or tl.startswith('tcl '):
                return 'ladder'
            if 'open' in tl or 'wimbledon' in tl or 'slam' in tl:
                return 'slam'
            return 'other'

        achievements = dict(ach_row) if ach_row else None
        top_achievements = json.loads(ach_row['top_achievements_json']) if ach_row and ach_row['top_achievements_json'] else []
        all_records = []
        for r in records_rows:
            rec = dict(r)
            t_name = rec.get('tournament_name') or ''
            rec['cge_url'] = get_cge_url(t_name)
            rec['category'] = get_tournament_category(t_name)
            all_records.append(rec)

        # Separate into individual seasons (standard view) vs career totals & Hall of Fame
        season_records = [r for r in all_records if not r.get('is_career_total')]
        career_records = [r for r in all_records if r.get('is_career_total')]

        # Default sort season_records by finish_date DESC
        season_records.sort(key=lambda r: str(r.get('finish_date') or ''), reverse=True)

        return render_template(
            'player_achievements.html',
            player=player,
            achievements=achievements,
            top_achievements=top_achievements,
            records=all_records,
            season_records=season_records,
            career_records=career_records
        )
    finally:
        conn.close()


@player_bp.route('/api/h2h/<player1>/<player2>')
def api_h2h(player1, player2):
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT match_id, tournament, date, player_count, player1, score1, player2, score2, '
            'player3, score3, player4, score4 '
            'FROM matches '
            'WHERE (player1 = ? OR player2 = ? OR player3 = ? OR player4 = ?) '
            '  AND (player1 = ? OR player2 = ? OR player3 = ? OR player4 = ?) '
            'ORDER BY date DESC, match_id DESC LIMIT 100',
            (player1, player1, player1, player1, player2, player2, player2, player2)
        ).fetchall()

        matches = []
        p1_wins = 0
        p2_wins = 0
        draws = 0

        for m in rows:
            participants = []
            for i in range(1, 5):
                p_col = m[f'player{i}']
                s_col = m[f'score{i}']
                if p_col and s_col is not None:
                    participants.append({'name': p_col, 'score': float(s_col)})
            participants.sort(key=lambda x: x['score'], reverse=True)

            p1_place = None
            p2_place = None
            for rank_idx, p in enumerate(participants, 1):
                if p['name'].lower() == player1.lower():
                    p1_place = rank_idx
                elif p['name'].lower() == player2.lower():
                    p2_place = rank_idx

            if p1_place and p2_place:
                if p1_place < p2_place:
                    p1_wins += 1
                elif p2_place < p1_place:
                    p2_wins += 1
                else:
                    draws += 1

            matches.append({
                'match_id': m['match_id'],
                'tournament': m['tournament'],
                'date': m['date'],
                'player_count': m['player_count'],
                'p1_place': p1_place,
                'p2_place': p2_place,
                'participants': participants
            })

        return {
            'player1': player1,
            'player2': player2,
            'total_matches': len(matches),
            'p1_wins': p1_wins,
            'p2_wins': p2_wins,
            'draws': draws,
            'matches': matches
        }
    finally:
        conn.close()


@player_bp.route('/player/<player_name>/matrix')
@player_bp.route('/player/<player_name>/modes')
def player_matrix(player_name):
    """Subpage displaying the complete 3x3 rating matrix across models and resets, filterable by year, with career peak year evaluation."""
    model_param = request.args.get('model')
    if model_param in VALID_MODELS:
        session['active_model'] = model_param
    active_model = session.get('active_model')
    if not active_model or active_model not in VALID_MODELS:
        active_model = 'glicko2_daneo'
        session['active_model'] = 'glicko2_daneo'

    format_param = request.args.get('format')
    if format_param is not None:
        try:
            fmt_int = int(format_param)
            if fmt_int in (0, 2, 3, 4):
                session['active_format'] = fmt_int
        except ValueError:
            pass
    active_format = session.get('active_format', 0)

    year_param = request.args.get('year')
    selected_year = None
    if year_param and year_param.isdigit():
        selected_year = int(year_param)

    conn = get_connection()
    try:
        lookup_name = KNOWN_PLAYER_ALIASES.get(player_name.lower(), player_name)
        player_row = conn.execute(
            'SELECT name, country_code, title, title_count, last_played, peak_title, peak_year FROM players WHERE LOWER(name) = LOWER(?)',
            (lookup_name,)
        ).fetchone()

        if not player_row:
            abort(404)
        player = dict(player_row)
        pk_t = player.get('peak_title')
        cr_t = player.get('title')
        player['is_peak_higher'] = bool(pk_t and player.get('peak_year') and (not cr_t or TITLE_ORDER.get(pk_t, 99) < TITLE_ORDER.get(cr_t, 99)))
        player_name = player['name']

        # Combinations: (model, reset_mode, db_key)
        model_keys = [
            ('glicko2_daneo', 'continuous', 'glicko2_daneo'),
            ('glicko2_daneo', 'softer', 'glicko2_daneo_softer'),
            ('glicko2_daneo', 'soft', 'glicko2_daneo_soft'),
            ('glicko2_std', 'continuous', 'glicko2_std'),
            ('glicko2_std', 'softer', 'glicko2_std_softer'),
            ('glicko2_std', 'soft', 'glicko2_std_soft'),
            ('glicko2_mp', 'continuous', 'glicko2_mp'),
            ('glicko2_mp', 'softer', 'glicko2_mp_softer'),
            ('glicko2_mp', 'soft', 'glicko2_mp_soft'),
            ('glicko2_adapt', 'continuous', 'glicko2_adapt'),
            ('glicko2_adapt', 'softer', 'glicko2_adapt_softer'),
            ('glicko2_adapt', 'soft', 'glicko2_adapt_soft'),
            ('whr', 'continuous', 'whr'),
            ('whr', 'softer', 'whr_softer'),
            ('whr', 'soft', 'whr_soft'),
        ]

        matrix_cells = {}
        if selected_year is not None:
            for base_m, r_mode, db_key in model_keys:
                snap_row = conn.execute(
                    'SELECT MAX(period_date) as max_d FROM rating_history WHERE model_type = ? AND player_count = ? AND period_date LIKE ?',
                    (db_key, active_format, f"{selected_year}%")
                ).fetchone()
                snap_d = snap_row['max_d'] if snap_row and snap_row['max_d'] else None

                r_val = None
                rd_val = None
                c_val = None
                rank_val = None

                if snap_d:
                    row = conn.execute(
                        'SELECT rating, rd, c_rating FROM rating_history WHERE model_type = ? AND player_count = ? AND period_date = ? AND player_name = ?',
                        (db_key, active_format, snap_d, player_name)
                    ).fetchone()
                    if row:
                        r_val = round(row['rating'], 1)
                        rd_val = round(row['rd'], 1)
                        c_val = round(row['c_rating'], 1)
                        rk_row = conn.execute(
                            'SELECT COUNT(*) + 1 FROM rating_history WHERE model_type = ? AND player_count = ? AND period_date = ? AND c_rating > ?',
                            (db_key, active_format, snap_d, row['c_rating'])
                        ).fetchone()
                        rank_val = rk_row[0] if rk_row else None

                matrix_cells[(base_m, r_mode)] = {
                    'rating': r_val,
                    'rd': rd_val,
                    'c_rating': c_val,
                    'rank': rank_val
                }
        else:
            for base_m, r_mode, db_key in model_keys:
                row = conn.execute(
                    'SELECT rating, rd, c_rating, rank, opponents_count, win_rate FROM player_ratings WHERE model_type = ? AND player_count = ? AND player_name = ?',
                    (db_key, active_format, player_name)
                ).fetchone()
                matrix_cells[(base_m, r_mode)] = {
                    'rating': round(row['rating'], 1) if row else None,
                    'rd': round(row['rd'], 1) if row else None,
                    'c_rating': round(row['c_rating'], 1) if row else None,
                    'rank': row['rank'] if row else None
                }

        # Yearly performance history
        yearly_rows = conn.execute(
            'SELECT year, opponents_count, wins, losses, draws, win_rate, career_opps, career_wins, career_losses, career_draws, career_win_rate '
            'FROM yearly_player_stats WHERE player_name = ? AND player_count = ? AND opponents_count > 0 ORDER BY year ASC',
            (player_name, active_format)
        ).fetchall()

        if not yearly_rows and active_format != 0:
            yearly_rows = conn.execute(
                'SELECT year, opponents_count, wins, losses, draws, win_rate, career_opps, career_wins, career_losses, career_draws, career_win_rate '
                'FROM yearly_player_stats WHERE player_name = ? AND player_count = 0 AND opponents_count > 0 ORDER BY year ASC',
                (player_name,)
            ).fetchall()

        career_history_table = []
        best_year = None
        best_year_score = -999999.0

        yearly_titles = get_player_yearly_titles(conn, player_name)
        p_peak_yr = player.get('peak_year')

        for yr_row in yearly_rows:
            y = yr_row['year']
            pk_row = conn.execute(
                'SELECT MAX(rating) as pk FROM rating_history WHERE player_name = ? AND player_count = ? AND period_date LIKE ?',
                (player_name, active_format if active_format in (2, 3, 4) else 0, f"{y}%")
            ).fetchone()
            peak_r = round(pk_row['pk'], 1) if pk_row and pk_row['pk'] else None

            snap_row = conn.execute(
                'SELECT rating, rd, c_rating FROM rating_history WHERE model_type = "glicko2_std" AND player_count = ? AND period_date LIKE ? AND player_name = ? ORDER BY period_date DESC LIMIT 1',
                (active_format if active_format in (2, 3, 4) else 0, f"{y}%", player_name)
            ).fetchone()

            w = yr_row['wins']
            wr = yr_row['win_rate']

            t_info = yearly_titles.get(y, {})
            y_title = t_info.get('title')
            y_title_name = t_info.get('title_name')

            bonus = TIER_BONUS.get(y_title, 0)
            if p_peak_yr and y == p_peak_yr:
                bonus += 30

            score = (w * 1.5) + (wr * 2.0) + ((peak_r - 1500) * 0.4 if peak_r else 0) + bonus

            entry = {
                'year': y,
                'opps': yr_row['opponents_count'],
                'wins': w,
                'losses': yr_row['losses'],
                'draws': yr_row['draws'],
                'win_rate': wr,
                'career_opps': yr_row['career_opps'],
                'career_wins': yr_row['career_wins'],
                'career_losses': yr_row['career_losses'],
                'career_draws': yr_row['career_draws'],
                'career_win_rate': yr_row['career_win_rate'],
                'peak_rating': peak_r,
                'year_end_rating': round(snap_row['rating'], 1) if snap_row else None,
                'score': round(score, 1),
                'is_wc': y_title == 'WC',
                'title': y_title,
                'title_name': y_title_name
            }
            career_history_table.append(entry)

            if score > best_year_score:
                best_year_score = score
                best_year = entry

        # Fallback if title is missing on best_year but player has peak_title
        if best_year and not best_year.get('title') and player.get('peak_title'):
            best_year['title'] = player['peak_title']
            best_year['title_name'] = TITLE_FULL_NAMES.get(player['peak_title'], player['peak_title'])
            if player['peak_title'] == 'WC':
                best_year['is_wc'] = True

        # History Chart comparing Continuous vs Soft vs Amplified for all models
        all_hist_rows = conn.execute(
            'SELECT model_type, period_date, rating '
            'FROM rating_history WHERE player_name = ? AND player_count = ? '
            'ORDER BY period_date ASC',
            (player_name, active_format)
        ).fetchall()

        dates_set = set()
        model_reset_series = {
            'glicko2_daneo': {'continuous': {}, 'softer': {}, 'soft': {}, 'amplified': {}},
            'glicko2_std': {'continuous': {}, 'soft': {}, 'amplified': {}, 'softer': {}},
            'glicko2_mp': {'continuous': {}, 'soft': {}, 'amplified': {}, 'softer': {}},
            'glicko2_adapt': {'continuous': {}, 'soft': {}, 'amplified': {}, 'softer': {}},
            'whr': {'continuous': {}, 'soft': {}, 'amplified': {}, 'softer': {}}
        }
        for hr in all_hist_rows:
            d = hr['period_date']
            m = hr['model_type']
            dates_set.add(d)
            for bm in ['glicko2_daneo', 'glicko2_std', 'glicko2_mp', 'glicko2_adapt', 'whr']:
                if m == bm:
                    model_reset_series[bm]['continuous'][d] = round(hr['rating'], 1)
                elif m == f"{bm}_softer":
                    model_reset_series[bm]['softer'][d] = round(hr['rating'], 1)
                elif m == f"{bm}_soft":
                    model_reset_series[bm]['soft'][d] = round(hr['rating'], 1)
                elif m == f"{bm}_amplified":
                    model_reset_series[bm]['amplified'][d] = round(hr['rating'], 1)

        sorted_dates = sorted(list(dates_set))
        active_series = model_reset_series.get(active_model, model_reset_series['glicko2_std'])
        chart_data = {
            'labels': sorted_dates,
            'active_model': active_model,
            'glicko2_daneo': {
                'continuous': [model_reset_series['glicko2_daneo']['continuous'].get(d) for d in sorted_dates],
                'softer': [model_reset_series['glicko2_daneo']['softer'].get(d) for d in sorted_dates],
                'soft': [model_reset_series['glicko2_daneo']['soft'].get(d) for d in sorted_dates]
            },
            'glicko2_std': {
                'continuous': [model_reset_series['glicko2_std']['continuous'].get(d) for d in sorted_dates],
                'soft': [model_reset_series['glicko2_std']['soft'].get(d) for d in sorted_dates],
                'amplified': [model_reset_series['glicko2_std']['amplified'].get(d) for d in sorted_dates]
            },
            'glicko2_mp': {
                'continuous': [model_reset_series['glicko2_mp']['continuous'].get(d) for d in sorted_dates],
                'soft': [model_reset_series['glicko2_mp']['soft'].get(d) for d in sorted_dates],
                'amplified': [model_reset_series['glicko2_mp']['amplified'].get(d) for d in sorted_dates]
            },
            'glicko2_adapt': {
                'continuous': [model_reset_series['glicko2_adapt']['continuous'].get(d) for d in sorted_dates],
                'soft': [model_reset_series['glicko2_adapt']['soft'].get(d) for d in sorted_dates],
                'amplified': [model_reset_series['glicko2_adapt']['amplified'].get(d) for d in sorted_dates]
            },
            'whr': {
                'continuous': [model_reset_series['whr']['continuous'].get(d) for d in sorted_dates],
                'soft': [model_reset_series['whr']['soft'].get(d) for d in sorted_dates],
                'amplified': [model_reset_series['whr']['amplified'].get(d) for d in sorted_dates]
            },
            # Compatibility keys for initial active model
            'continuous': [active_series['continuous'].get(d) for d in sorted_dates],
            'soft': [active_series['soft'].get(d) for d in sorted_dates],
            'amplified': [active_series.get('amplified', {}).get(d) for d in sorted_dates]
        }

        available_years = [r['year'] for r in yearly_rows]

        return render_template(
            'player_matrix.html',
            player=player,
            matrix_cells=matrix_cells,
            career_history=career_history_table,
            best_year=best_year,
            selected_year=selected_year,
            available_years=available_years,
            chart_json=json.dumps(chart_data),
            active_model=active_model,
            active_model_name=VALID_MODELS.get(active_model, 'Glicko-2 Standard'),
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
            reset_modes=VALID_RESET_MODES
        )
    finally:
        conn.close()
