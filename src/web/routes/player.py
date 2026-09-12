import json
from flask import Blueprint, render_template, abort, request, session
from src.data.db import get_connection

player_bp = Blueprint('player', __name__)

VALID_MODELS = {
    'glicko2_std': 'Glicko-2 Standard',
    'glicko2_mp': 'Glicko-2 MP-Weighted',
    'whr': 'Whole-History Rating'
}

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
    active_model = session.get('active_model', 'glicko2_std')

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

    conn = get_connection()
    try:
        # Player metadata (with alias and case-insensitive support)
        lookup_name = KNOWN_PLAYER_ALIASES.get(player_name.lower(), player_name)
        player = conn.execute(
            'SELECT name, country_code, title, title_count, last_played FROM players WHERE LOWER(name) = LOWER(?)',
            (lookup_name,)
        ).fetchone()

        if not player:
            # Try to see if player exists in matches
            exists = conn.execute(
                'SELECT player1 FROM matches WHERE LOWER(player1)=LOWER(?) OR LOWER(player2)=LOWER(?) OR LOWER(player3)=LOWER(?) OR LOWER(player4)=LOWER(?) LIMIT 1',
                (lookup_name, lookup_name, lookup_name, lookup_name)
            ).fetchone()
            if not exists:
                abort(404)
            player = {'name': lookup_name, 'country_code': None, 'title': None, 'title_count': 0, 'last_played': None}

        player_name = player['name']

        # Fetch ratings for all 3 models in this format
        ratings_rows = conn.execute(
            'SELECT model_type, rating, rd, sigma, c_rating, rank, rank_delta, opponents_count, wins, losses, draws, win_rate '
            'FROM player_ratings WHERE player_name = ? AND player_count = ?',
            (player_name, active_format)
        ).fetchall()

        ratings_by_model = {r['model_type']: dict(r) for r in ratings_rows}

        # Fetch history points for Chart.js across all 3 models in this format
        hist_rows = conn.execute(
            'SELECT model_type, period_date, rating, rd, c_rating '
            'FROM rating_history WHERE player_name = ? AND player_count = ? ORDER BY period_date ASC',
            (player_name, active_format)
        ).fetchall()

        # Build unified chart data
        dates_set = set()
        model_series = {'glicko2_std': {}, 'glicko2_mp': {}, 'whr': {}}
        for r in hist_rows:
            d = r['period_date']
            m = r['model_type']
            dates_set.add(d)
            if m in model_series:
                model_series[m][d] = round(r['rating'], 1)

        sorted_dates = sorted(list(dates_set))
        chart_data = {
            'labels': sorted_dates,
            'glicko2_std': [model_series['glicko2_std'].get(d) for d in sorted_dates],
            'glicko2_mp': [model_series['glicko2_mp'].get(d) for d in sorted_dates],
            'whr': [model_series['whr'].get(d) for d in sorted_dates]
        }

        # Fetch recent matches (last 30)
        match_rows = conn.execute(
            'SELECT match_id, tournament, date, player_count, player1, score1, player2, score2, '
            'player3, score3, player4, score4 '
            'FROM matches '
            'WHERE player1=? OR player2=? OR player3=? OR player4=? '
            'ORDER BY date DESC, match_id DESC LIMIT 30',
            (player_name, player_name, player_name, player_name)
        ).fetchall()

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

            recent_matches.append({
                'match_id': m['match_id'],
                'tournament': m['tournament'],
                'date': m['date'],
                'player_count': m['player_count'],
                'placement': placement,
                'participants': participants
            })

        # Head-to-Head records against rivals (expanded to all opponents)
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
            'SELECT total_titles, international_titles, intermezzo_titles, royal_league_titles, other_titles, '
            'gold_medals, silver_medals, bronze_medals, summary_text, top_achievements_json '
            'FROM player_achievements WHERE player_name = ?',
            (player_name,)
        ).fetchone()

        achievements = dict(ach_row) if ach_row else None
        top_achievements = json.loads(ach_row['top_achievements_json']) if ach_row and ach_row['top_achievements_json'] else []

        # Dynamic narrative insights and peak calculations
        std_r = ratings_by_model.get('glicko2_std', {})
        mp_r = ratings_by_model.get('glicko2_mp', {})
        whr_r = ratings_by_model.get('whr', {})

        peaks = {}
        for m_key, s_dict in model_series.items():
            if s_dict:
                best_date = max(s_dict.keys(), key=lambda d: s_dict[d])
                peak_rating = s_dict[best_date]
                rank_query = conn.execute(
                    'SELECT COUNT(*) + 1 FROM rating_history '
                    'WHERE model_type = ? AND player_count = ? AND period_date = ? AND rating > ?',
                    (m_key, active_format, best_date, peak_rating)
                ).fetchone()
                peak_rank = rank_query[0] if rank_query else None
                peaks[m_key] = {'rating': peak_rating, 'rank': peak_rank, 'date': best_date}

        divergence_notes = []
        if std_r and mp_r:
            diff_mp = std_r.get('rating', 1500) - mp_r.get('rating', 1500)
            if diff_mp > 15:
                divergence_notes.append(
                    f"Rating adjusts downward by {diff_mp:.1f} pts under MP-Weighted, reflecting calibration for multiplayer (3p/4p) play where naive dueling over-accumulates confidence."
                )
            elif diff_mp < -15:
                divergence_notes.append(
                    f"Rating gains {abs(diff_mp):.1f} pts under MP-Weighted, demonstrating high conversion efficiency in complex multiplayer tables."
                )
            else:
                divergence_notes.append(
                    "Standard and MP-Weighted ratings are tightly aligned, indicating balanced duel and multiplayer tournament exposure."
                )

        if std_r and whr_r:
            diff_whr = whr_r.get('rating', 1500) - std_r.get('rating', 1500)
            if diff_whr > 20:
                divergence_notes.append(
                    f"WHR evaluates career strength {diff_whr:.1f} pts higher retrospectively, crediting resilient play across high-variance tournament seasons."
                )
            elif diff_whr < -20:
                divergence_notes.append(
                    f"WHR smooths out localized hot streaks by {abs(diff_whr):.1f} pts, grounding historical trajectory against opponents' lifetime records."
                )
            else:
                divergence_notes.append(
                    "WHR retrospective reconstruction confirms the forward Glicko-2 trajectory with exceptional fidelity."
                )

        career_summary = achievements['summary_text'] if achievements and achievements.get('summary_text') else None

        narrative = {
            'peaks': peaks,
            'divergence': divergence_notes,
            'career_summary': career_summary
        }

        return render_template(
            'player.html',
            player=player,
            ratings=ratings_by_model,
            chart_json=json.dumps(chart_data),
            recent_matches=recent_matches,
            h2h=h2h_list,
            narrative=narrative,
            achievements=achievements,
            top_achievements=top_achievements,
            active_model=active_model,
            models=VALID_MODELS
        )
    finally:
        conn.close()


@player_bp.route('/player/<player_name>/achievements')
def player_achievements(player_name):
    conn = get_connection()
    try:
        lookup_name = KNOWN_PLAYER_ALIASES.get(player_name.lower(), player_name)
        player = conn.execute(
            'SELECT name, country_code, title, title_count, last_played FROM players WHERE LOWER(name) = LOWER(?)',
            (lookup_name,)
        ).fetchone()
        if not player:
            abort(404)
        player_name = player['name']

        ach_row = conn.execute(
            'SELECT * FROM player_achievements WHERE player_name = ?',
            (player_name,)
        ).fetchone()

        records_rows = conn.execute(
            'SELECT record_id, tournament_name, season, division, placement, points, medal, details, finish_date, is_career_total '
            'FROM tournament_records WHERE player_name = ? '
            'ORDER BY finish_date DESC, record_id DESC',
            (player_name,)
        ).fetchall()

        achievements = dict(ach_row) if ach_row else None
        top_achievements = json.loads(ach_row['top_achievements_json']) if ach_row and ach_row['top_achievements_json'] else []
        all_records = [dict(r) for r in records_rows]

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
