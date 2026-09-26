from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session, url_for, abort
from src.data.db import get_connection, ensure_yearly_stats

leaderboard_bp = Blueprint('leaderboard', __name__)

VALID_MODELS = {
    'glicko2_daneo': 'GlickoD',
    'glicko2_std': 'Glicko-2 Standard',
    'glicko2_mp': 'Glicko-2 MP-Weighted',
    'glicko2_adapt': 'Glicko-2 Adaptive-T',
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
        'id': 'continuous',
        'name': 'Continuous (Career)',
        'short': 'Career',
        'desc': 'Standard uninterrupted career rating trajectory across all tournament history'
    },
    'softer': {
        'id': 'softer',
        'name': 'Season Reset',
        'short': 'Season Reset',
        'desc': 'Gentle annual reset balancing career achievement with current season form'
    }
}

AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017]

WORLD_CHAMPIONS = {
    2026: {'player': 'a440', 'title': 'Reigning World Champion'},
    2025: {'player': 'a440', 'title': 'World Champion'},
    2024: {'player': 'Martin_Pecheur', 'title': 'World Champion'},
    2023: {'player': 'Weidenbaum', 'title': 'World Champion'}
}

INACTIVE_CUTOFF_DATE = '2025-05-31'  # Players without games in 12 months (<= 2025-05-31) are inactive

@leaderboard_bp.route('/')
@leaderboard_bp.route('/ratings')
@leaderboard_bp.route('/leaderboard')
def index():
    return render_leaderboard(year=None)


@leaderboard_bp.route('/ratings/<int:year>')
@leaderboard_bp.route('/leaderboard/<int:year>')
def yearly(year):
    return render_leaderboard(year=year)


@leaderboard_bp.route('/api/players/suggest')
def suggest_players():
    """Returns matching player suggestions for live search bar prefiltering."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return {'suggestions': []}

    conn = get_connection()
    try:
        like_prefix = f"{q.lower()}%"
        like_sub = f"%{q.lower()}%"
        query = """
            SELECT name, country_code, title
            FROM players
            WHERE LOWER(name) LIKE ?
            ORDER BY
                CASE
                    WHEN LOWER(name) = ? THEN 0
                    WHEN LOWER(name) LIKE ? THEN 1
                    ELSE 2
                END,
                name ASC
            LIMIT 12
        """
        rows = conn.execute(query, (like_sub, q.lower(), like_prefix)).fetchall()
        suggestions = [
            {
                'name': r['name'],
                'country_code': r['country_code'] or '',
                'title': r['title'] or ''
            }
            for r in rows
        ]
        return {'suggestions': suggestions}
    finally:
        conn.close()


def render_leaderboard(year=None):
    if year is not None and year not in AVAILABLE_YEARS:
        abort(404)

    # 1. Model selection
    model_param = request.args.get('model')
    if model_param and model_param in VALID_MODELS:
        session['active_model'] = model_param
    active_model = session.get('active_model')
    if not active_model or active_model not in VALID_MODELS:
        active_model = 'glicko2_daneo'
        session['active_model'] = 'glicko2_daneo'

    # 2. Season Reset Mode selection (continuous, softer)
    reset_param = request.args.get('reset_mode')
    if reset_param in ('soft', 'amplified'):
        reset_param = 'softer'
    if reset_param in VALID_RESET_MODES:
        session['active_reset_mode'] = reset_param
    active_reset_mode = session.get('active_reset_mode')
    if not active_reset_mode or active_reset_mode not in VALID_RESET_MODES:
        active_reset_mode = 'continuous'
        session['active_reset_mode'] = 'continuous'

    # Retrospective Prior Calibration (Option A) lever
    retro_param = request.args.get('retro')
    if retro_param is not None:
        session['active_retro'] = (retro_param.lower() in ('1', 'true', 'yes'))
    active_retro = session.get('active_retro', False)

    # Effective database model key
    if active_model in ('glicko2_daneo', 'whr'):
        db_model = f"{active_model}_{active_reset_mode}" if active_reset_mode != 'continuous' else active_model
    else:
        if active_retro:
            db_model = f"{active_model}_{active_reset_mode}_retro" if active_reset_mode != 'continuous' else f"{active_model}_retro"
        else:
            db_model = f"{active_model}_{active_reset_mode}" if active_reset_mode != 'continuous' else active_model

    # 3. Format selection (0=All, 2=2p, 3=3p, 4=4p)
    format_param = request.args.get('format')
    if format_param is not None:
        try:
            fmt_int = int(format_param)
            if fmt_int in VALID_FORMATS:
                session['active_format'] = fmt_int
        except ValueError:
            pass
    active_format = session.get('active_format', 0)

    # 3. Status filter: 'active' (default), 'all', 'inactive'
    status = request.args.get('status', 'active').lower()
    if status not in ('active', 'all', 'inactive'):
        status = 'active'

    # 4. RB48 Deltas timeframe window
    delta_window = request.args.get('delta', 'none').lower()
    if delta_window not in ('none', 'last_update', 'game', 'month', 'quarter', 'year', 'baseline'):
        delta_window = 'none'

    # 5. Minimum matches / opponents filter (default 30 for all-time, 0 for yearly)
    min_opps_param = request.args.get('min_opps')
    if min_opps_param is not None:
        try:
            min_opps = max(0, int(min_opps_param.strip()))
        except ValueError:
            min_opps = 0 if year is not None else 30
    else:
        min_opps = 0 if year is not None else 30

    # 6. Seasonal vs Career Stats Switcher for yearly view
    stats_view = request.args.get('stats_view', 'season').lower()
    if stats_view not in ('season', 'career'):
        stats_view = 'season'

    search = (request.args.get('search') or '').strip()
    title_filter = (request.args.get('title') or '').strip()
    sort_by = request.args.get('sort', 'rank')
    order = request.args.get('order', 'asc').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 50

    conn = get_connection()
    try:
        ensure_yearly_stats(conn)

        year_info = None
        if year is not None:
            # Look up year-end snapshot date for active model & format
            snap_row = conn.execute(
                "SELECT MAX(period_date) as max_date FROM rating_history WHERE model_type = ? AND player_count = ? AND period_date LIKE ?",
                (db_model, active_format, f"{year}%")
            ).fetchone()
            snapshot_date = snap_row['max_date'] if snap_row and snap_row['max_date'] else None

            # Fallback across any model/format if current format had no period
            if not snapshot_date:
                fallback_snap = conn.execute(
                    "SELECT MAX(period_date) as max_date FROM rating_history WHERE period_date LIKE ?",
                    (f"{year}%",)
                ).fetchone()
                snapshot_date = fallback_snap['max_date'] if fallback_snap and fallback_snap['max_date'] else f"{year}-12-31"

            match_row = conn.execute(
                "SELECT COUNT(*) as total FROM matches WHERE date LIKE ?",
                (f"{year}%",)
            ).fetchone()
            total_year_matches = match_row['total'] if match_row else 0

            year_info = {
                'year': year,
                'snapshot_date': snapshot_date,
                'total_matches': total_year_matches,
                'world_champion': WORLD_CHAMPIONS.get(year),
                'stats_view': stats_view
            }

            where_clauses = ['rh.model_type = ?', 'rh.player_count = ?', 'rh.period_date = ?']
            pool_params = [year, active_format, db_model, active_format, snapshot_date]

            opp_col = 'COALESCE(yps.career_opps, 0)' if stats_view == 'career' else 'COALESCE(yps.opponents_count, 0)'
            wins_col = 'COALESCE(yps.career_wins, 0)' if stats_view == 'career' else 'COALESCE(yps.wins, 0)'
            losses_col = 'COALESCE(yps.career_losses, 0)' if stats_view == 'career' else 'COALESCE(yps.losses, 0)'
            draws_col = 'COALESCE(yps.career_draws, 0)' if stats_view == 'career' else 'COALESCE(yps.draws, 0)'
            winrate_col = 'COALESCE(yps.career_win_rate, 0.0)' if stats_view == 'career' else 'COALESCE(yps.win_rate, 0.0)'

            if min_opps > 0:
                where_clauses.append(f'{opp_col} >= ?')
                pool_params.append(min_opps)

            if status == 'active':
                where_clauses.append('COALESCE(yps.opponents_count, 0) > 0')
            elif status == 'inactive':
                where_clauses.append('COALESCE(yps.opponents_count, 0) == 0')

            if title_filter and title_filter != 'ALL':
                where_clauses.append('p.title = ?')
                pool_params.append(title_filter)

            where_sql = ' AND '.join(where_clauses)

            pool_sql = (
                'SELECT ROW_NUMBER() OVER (ORDER BY rh.c_rating DESC) as rank, '
                '0 as rank_delta, rh.player_name, p.country_code, p.title, p.title_count, p.badge_reason, '
                'rh.rating, rh.rd, 0.0 as sigma, rh.c_rating, '
                f'{opp_col} as opponents_count, '
                f'{wins_col} as wins, {losses_col} as losses, '
                f'{draws_col} as draws, {winrate_col} as win_rate, '
                'yps.last_played, '
                'ROW_NUMBER() OVER (ORDER BY rh.c_rating DESC) as display_rank '
                'FROM rating_history rh '
                'LEFT JOIN players p ON rh.player_name = p.name '
                'LEFT JOIN yearly_player_stats yps ON yps.year = ? AND yps.player_count = ? AND yps.player_name = rh.player_name '
                'WHERE ' + where_sql
            )
        else:
            # All-Time / Live Leaderboard
            where_clauses = ['pr.model_type = ?', 'pr.player_count = ?']
            pool_params = [db_model, active_format]

            if min_opps > 0:
                where_clauses.append('pr.opponents_count >= ?')
                pool_params.append(min_opps)

            if status == 'active':
                where_clauses.append('pr.last_played > ?')
                pool_params.append(INACTIVE_CUTOFF_DATE)
            elif status == 'inactive':
                where_clauses.append('(pr.last_played IS NULL OR pr.last_played <= ?)')
                pool_params.append(INACTIVE_CUTOFF_DATE)

            if title_filter and title_filter != 'ALL':
                where_clauses.append('p.title = ?')
                pool_params.append(title_filter)

            where_sql = ' AND '.join(where_clauses)

            pool_sql = (
                'SELECT pr.rank, pr.rank_delta, pr.player_name, p.country_code, p.title, p.title_count, p.badge_reason, '
                'pr.rating, pr.rd, pr.sigma, pr.c_rating, pr.opponents_count, pr.wins, pr.losses, pr.draws, '
                'pr.win_rate, pr.last_played, '
                'ROW_NUMBER() OVER (ORDER BY pr.c_rating DESC) as display_rank '
                'FROM player_ratings pr '
                'LEFT JOIN players p ON pr.player_name = p.name '
                'WHERE ' + where_sql
            )

        sort_map = {
            'rank': 'display_rank',
            'rating': 'rating',
            'c_rating': 'c_rating',
            'opps': 'opponents_count',
            'win_rate': 'win_rate',
            'name': 'player_name',
            'last_played': 'last_played'
        }
        col_sort = sort_map.get(sort_by, 'display_rank')
        sort_dir = 'DESC' if order == 'desc' else 'ASC'

        jump_to_player = None

        if search:
            if ',' in search:
                # Comma-separated multi-player search: show only these selected players
                names = [n.strip() for n in search.split(',') if n.strip()]
                or_clauses = ['(LOWER(player_name) LIKE ? OR LOWER(country_code) = ?)' for _ in names]
                or_params = []
                for n in names:
                    or_params.extend([f"%{n.lower()}%", n.lower()])

                filter_sql = (
                    f"WITH pool AS ({pool_sql}) "
                    f"SELECT * FROM pool WHERE {' OR '.join(or_clauses)} "
                    f"ORDER BY {col_sort} {sort_dir}"
                )
                rows = conn.execute(filter_sql, pool_params + or_params).fetchall()
                total_count = len(rows)
                page = 1
                total_pages = 1
            else:
                # Single search term: check if it matches a unique player
                match_sql = (
                    f"WITH pool AS ({pool_sql}) "
                    f"SELECT * FROM pool WHERE LOWER(player_name) LIKE ? OR LOWER(country_code) = ?"
                )
                matches = conn.execute(match_sql, pool_params + [f"%{search.lower()}%", search.lower()]).fetchall()

                if len(matches) == 1 or any(m['player_name'].lower() == search.lower() for m in matches):
                    # Single player match: jump to their exact position in the full leaderboard
                    if any(m['player_name'].lower() == search.lower() for m in matches):
                        target_p = next(m for m in matches if m['player_name'].lower() == search.lower())
                    else:
                        target_p = matches[0]

                    jump_to_player = target_p['player_name']
                    pos_row = conn.execute(
                        f"WITH pool AS ({pool_sql}) "
                        f"SELECT pos FROM (SELECT player_name, ROW_NUMBER() OVER (ORDER BY {col_sort} {sort_dir}) as pos FROM pool) "
                        f"WHERE player_name = ?",
                        pool_params + [target_p['player_name']]
                    ).fetchone()

                    if pos_row:
                        target_pos = pos_row['pos']
                        page = (target_pos - 1) // per_page + 1

                    count_row = conn.execute(f"WITH pool AS ({pool_sql}) SELECT COUNT(*) as total FROM pool", pool_params).fetchone()
                    total_count = count_row['total'] if count_row else 0
                    total_pages = max(1, (total_count + per_page - 1) // per_page)
                    offset = (page - 1) * per_page

                    query_sql = (
                        f"WITH pool AS ({pool_sql}) "
                        f"SELECT * FROM pool ORDER BY {col_sort} {sort_dir} LIMIT ? OFFSET ?"
                    )
                    rows = conn.execute(query_sql, pool_params + [per_page, offset]).fetchall()
                else:
                    # Multiple players matched partial string: show only matching players with true display_rank
                    count_sql = (
                        f"WITH pool AS ({pool_sql}) "
                        f"SELECT COUNT(*) as total FROM pool WHERE LOWER(player_name) LIKE ? OR LOWER(country_code) = ?"
                    )
                    total_count = conn.execute(count_sql, pool_params + [f"%{search.lower()}%", search.lower()]).fetchone()['total']
                    total_pages = max(1, (total_count + per_page - 1) // per_page)
                    offset = (page - 1) * per_page

                    query_sql = (
                        f"WITH pool AS ({pool_sql}) "
                        f"SELECT * FROM pool WHERE LOWER(player_name) LIKE ? OR LOWER(country_code) = ? "
                        f"ORDER BY {col_sort} {sort_dir} LIMIT ? OFFSET ?"
                    )
                    rows = conn.execute(query_sql, pool_params + [f"%{search.lower()}%", search.lower(), per_page, offset]).fetchall()
        else:
            # Standard leaderboard view
            count_sql = f"WITH pool AS ({pool_sql}) SELECT COUNT(*) as total FROM pool"
            total_count = conn.execute(count_sql, pool_params).fetchone()['total']
            total_pages = max(1, (total_count + per_page - 1) // per_page)
            offset = (page - 1) * per_page

            query_sql = f"WITH pool AS ({pool_sql}) SELECT * FROM pool ORDER BY {col_sort} {sort_dir} LIMIT ? OFFSET ?"
            rows = conn.execute(query_sql, pool_params + [per_page, offset]).fetchall()

        # Convert rows to mutable dictionaries to attach delta and active status
        player_list = []
        player_names = [r['player_name'] for r in rows]

        # Pre-fetch deltas if requested
        deltas_by_player = {}
        if delta_window != 'none' and player_names:
            placeholders = ','.join('?' * len(player_names))
            if year is not None and year > 2017:
                prev_snap_row = conn.execute(
                    "SELECT MAX(period_date) as max_date FROM rating_history WHERE model_type = ? AND player_count = ? AND period_date LIKE ?",
                    (db_model, active_format, f"{year - 1}%")
                ).fetchone()
                if prev_snap_row and prev_snap_row['max_date']:
                    prev_date = prev_snap_row['max_date']
                    hist_rows = conn.execute(
                        f"SELECT player_name, rating, rd, c_rating FROM rating_history "
                        f"WHERE model_type = ? AND player_count = ? AND period_date = ? "
                        f"AND player_name IN ({placeholders})",
                        [db_model, active_format, prev_date] + player_names
                    ).fetchall()
                    for hr in hist_rows:
                        deltas_by_player[hr['player_name']] = {
                            'hist_c': hr['c_rating'],
                            'hist_r': hr['rating'],
                            'hist_rd': hr['rd']
                        }
            elif year is None:
                if delta_window == 'baseline':
                    base_rows = conn.execute(
                        f"SELECT player_name, rank_delta, c_rating_delta, rating_delta, rd_delta, opps_delta, win_rate_delta "
                        f"FROM official_baseline WHERE player_name IN ({placeholders})",
                        player_names
                    ).fetchall()
                    for br in base_rows:
                        deltas_by_player[br['player_name']] = {
                            'c_rating': br['c_rating_delta'],
                            'rating': br['rating_delta'],
                            'rd': br['rd_delta'],
                            'rank': int(br['rank_delta']) if br['rank_delta'] is not None else 0,
                            'opps': int(br['opps_delta']) if br['opps_delta'] is not None else 0,
                            'win_rate': br['win_rate_delta']
                        }
                else:
                    if delta_window == 'last_update':
                        # 1. Check webmaster configured delta baseline
                        delta_cfg = conn.execute("SELECT cutoff_date FROM delta_config WHERE id = 1 AND cutoff_date IS NOT NULL").fetchone()
                        if delta_cfg and delta_cfg['cutoff_date']:
                            cutoff = delta_cfg['cutoff_date']
                        else:
                            pu_row = conn.execute(
                                "SELECT cutoff_date FROM pipeline_updates WHERE cutoff_date IS NOT NULL ORDER BY id DESC LIMIT 1"
                            ).fetchone()
                            if pu_row and pu_row['cutoff_date']:
                                cutoff = pu_row['cutoff_date']
                            else:
                                # Dynamic penultimate period snapshot
                                p_rows = conn.execute(
                                    "SELECT DISTINCT period_date FROM rating_history WHERE model_type = ? AND player_count = ? ORDER BY period_date DESC LIMIT 2",
                                    (db_model, active_format)
                                ).fetchall()
                                cutoff = p_rows[1]['period_date'] if len(p_rows) >= 2 else (p_rows[0]['period_date'] if p_rows else '2026-03-01')
                    else:
                        cutoff_map = {
                            'game': '2026-05-15',
                            'month': '2026-05-01',
                            'quarter': '2026-03-01',
                            'year': '2025-05-31'
                        }
                        cutoff = cutoff_map.get(delta_window, '2026-03-01')
                    hist_rows = conn.execute(
                        f"SELECT player_name, period_date, rating, rd, c_rating "
                        f"FROM rating_history "
                        f"WHERE model_type = ? AND player_count = ? AND period_date <= ? "
                        f"AND player_name IN ({placeholders}) "
                        f"ORDER BY period_date DESC",
                        [db_model, active_format, cutoff] + player_names
                    ).fetchall()

                    seen = set()
                    for hr in hist_rows:
                        pn = hr['player_name']
                        if pn not in seen:
                            seen.add(pn)
                            deltas_by_player[pn] = {
                                'hist_c': hr['c_rating'],
                                'hist_r': hr['rating'],
                                'hist_rd': hr['rd']
                            }

        # Build player dicts
        for r in rows:
            p = dict(r)
            if year is not None:
                p['is_active'] = bool(p.get('opponents_count', 0) > 0)
            else:
                lp = p.get('last_played')
                p['is_active'] = bool(lp and lp > INACTIVE_CUTOFF_DATE)

            # Provisional calibration status: < 15 matches and not inactive > 1 year
            p['is_calibrating'] = bool(p.get('opponents_count', 0) < 15 and p['is_active'])

            # Attach delta
            if delta_window != 'none':
                d_info = deltas_by_player.get(p['player_name'])
                if delta_window == 'baseline' and d_info and 'c_rating' in d_info:
                    p['delta'] = d_info
                elif d_info and 'hist_c' in d_info:
                    p['delta'] = {
                        'c_rating': round(p['c_rating'] - d_info['hist_c'], 2),
                        'rating': round(p['rating'] - d_info['hist_r'], 2),
                        'rd': round(p['rd'] - d_info['hist_rd'], 2),
                        'rank': 0,
                        'opps': 0,
                        'win_rate': 0.0
                    }
                else:
                    p['delta'] = {'c_rating': 0.0, 'rating': 0.0, 'rd': 0.0, 'rank': 0, 'opps': 0, 'win_rate': 0.0}
            else:
                p['delta'] = None

            player_list.append(p)

        titles_rows = conn.execute('SELECT DISTINCT title FROM players WHERE title IS NOT NULL').fetchall()
        title_order = {'GM': 1, 'M': 2, 'P': 3, 'G': 4}
        available_titles = sorted([r['title'] for r in titles_rows if r['title']], key=lambda t: title_order.get(t, 99))

        def make_url(extra_params):
            args = request.args.to_dict()
            args.update(extra_params)
            if year is not None:
                return url_for('leaderboard.yearly', year=year, **args)
            return url_for('leaderboard.index', **args)

        return render_template(
            'leaderboard.html',
            players=player_list,
            active_model=active_model,
            active_model_name=VALID_MODELS.get(active_model, 'Glicko-2 Standard'),
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
            reset_mode=active_reset_mode,
            reset_modes=VALID_RESET_MODES,
            active_retro=active_retro,
            status=status,
            delta_window=delta_window,
            min_opps=min_opps,
            jump_to_player=jump_to_player,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            search=search,
            title_filter=title_filter,
            available_titles=available_titles,
            sort_by=sort_by,
            order=order,
            selected_year=year,
            available_years=AVAILABLE_YEARS,
            year_info=year_info,
            stats_view=stats_view,
            make_url=make_url
        )
    finally:
        conn.close()
