from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session
from src.data.db import get_connection

leaderboard_bp = Blueprint('leaderboard', __name__)

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

INACTIVE_CUTOFF_DATE = '2025-05-31'  # Players without games in 12 months (<= 2025-05-31) are inactive

@leaderboard_bp.route('/')
@leaderboard_bp.route('/leaderboard')
def index():
    # 1. Model selection
    model_param = request.args.get('model')
    if model_param in VALID_MODELS:
        session['active_model'] = model_param
    active_model = session.get('active_model', 'glicko2_std')

    # 2. Format selection (0=All, 2=2p, 3=3p, 4=4p)
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

    # 5. Minimum matches / opponents filter (default 30)
    min_opps_param = request.args.get('min_opps')
    if min_opps_param is not None:
        try:
            min_opps = max(0, int(min_opps_param.strip()))
        except ValueError:
            min_opps = 30
    else:
        min_opps = 30

    search = (request.args.get('search') or '').strip()
    title_filter = (request.args.get('title') or '').strip()
    sort_by = request.args.get('sort', 'rank')
    order = request.args.get('order', 'asc').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 50

    conn = get_connection()
    try:
        where_clauses = ['pr.model_type = ?', 'pr.player_count = ?']
        pool_params = [active_model, active_format]

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

        pool_sql = (
            'SELECT pr.rank, pr.rank_delta, pr.player_name, p.country_code, p.title, p.title_count, '
            'pr.rating, pr.rd, pr.sigma, pr.c_rating, pr.opponents_count, pr.wins, pr.losses, pr.draws, '
            'pr.win_rate, pr.last_played, '
            'ROW_NUMBER() OVER (ORDER BY pr.c_rating DESC) as display_rank '
            'FROM player_ratings pr '
            'LEFT JOIN players p ON pr.player_name = p.name '
            'WHERE ' + where_sql
        )

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
                cutoff_map = {
                    'last_update': '2026-03-01',
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
                    [active_model, active_format, cutoff] + player_names
                ).fetchall()

                # Pick latest record <= cutoff for each player
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
            lp = p.get('last_played')
            p['is_active'] = bool(lp and lp > INACTIVE_CUTOFF_DATE)

            # Attach delta
            if delta_window != 'none':
                d_info = deltas_by_player.get(p['player_name'])
                if delta_window == 'baseline' and d_info:
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

        return render_template(
            'leaderboard.html',
            players=player_list,
            active_model=active_model,
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
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
            order=order
        )
    finally:
        conn.close()
