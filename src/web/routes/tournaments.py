"""Tournaments Hub and Dedicated Series Pages for TTA-Glicko2-WHR.

Provides comprehensive coverage of official TTA tournaments:
- Rulebooks & Format Synopses
- Historical Season Counts & Participation Metrics
- Dedicated Trophyboards & Halls of Fame (from official records)
- Fact-based Success Stories & Highlights for Master+ (M+) Profiles
- All-Time Highest Scoring Division Records from database match history
"""
from flask import Blueprint, render_template, abort
import re
from collections import defaultdict
from src.data.db import get_connection

tournaments_bp = Blueprint('tournaments', __name__, url_prefix='/tournaments')

from src.web.routes.hall_of_fame import TOURNAMENT_SERIES, get_populated_tournament_series


def get_tournament_records(slug, limit=10):
    """Fetch all-time highest scoring individual games in the highest division."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if slug == 'international':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'International%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'International%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'International%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'International%' AND player4 IS NOT NULL
                )
                WHERE tournament LIKE '%Master 1%' OR tournament LIKE '%Diamond%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'intermezzo':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Intermezzo%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Intermezzo%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Intermezzo%' AND player3 IS NOT NULL
                )
                WHERE tournament LIKE '%Master 1%' OR tournament LIKE '%Grandmaster 1%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'royal_league':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'RL_%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'RL_%'
                )
                WHERE tournament LIKE '%Emperor%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'worlds':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Worlds%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Worlds%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Worlds%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'Worlds%' AND player4 IS NOT NULL
                )
                WHERE tournament LIKE '%Stage 4%' OR tournament LIKE '%Final%' OR tournament LIKE '%Upper%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'grand_slams':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Wimbledon%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Wimbledon%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Wimbledon%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'Wimbledon%' AND player4 IS NOT NULL
                )
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'ladders':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%' AND player3 IS NOT NULL
                )
                ORDER BY score DESC LIMIT ?
            """
        else:
            return []
        cur.execute(query, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_seasonal_points_records(slug, limit=10):
    """Fetch all-time highest scoring season campaigns in the premier division."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute('''
            SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
            FROM matches
        ''').fetchall()

        def assign_points(scores, p_count):
            scores.sort(key=lambda x: x[1], reverse=True)
            if p_count == 4:
                std_pts = [6.0, 3.0, 1.0, 0.0]
            elif p_count == 3:
                std_pts = [5.0, 2.0, 0.0]
            else:
                std_pts = [2.0, 0.0]
            from collections import defaultdict
            groups = defaultdict(list)
            for p, s in scores:
                groups[s].append(p)
            res = []
            idx = 0
            for s in sorted(groups.keys(), reverse=True):
                plist = groups[s]
                k = len(plist)
                pts_chunk = sum(std_pts[idx : idx + k])
                pts_each = pts_chunk / k
                for p in plist:
                    res.append((p, pts_each))
                idx += k
            return res

        campaigns = defaultdict(lambda: {'pts': 0.0, 'games': 0, 'wins': 0, '2nd': 0, 'div': 'Premier', 'date': ''})

        for r in rows:
            t = r['tournament'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0]
            p_count = r['player_count'] if isinstance(r, dict) or hasattr(r, 'keys') else (r[2] or 4)
            p1 = r['player1'] if isinstance(r, dict) or hasattr(r, 'keys') else r[3]
            s1 = r['score1'] if isinstance(r, dict) or hasattr(r, 'keys') else r[4]
            p2 = r['player2'] if isinstance(r, dict) or hasattr(r, 'keys') else r[5]
            s2 = r['score2'] if isinstance(r, dict) or hasattr(r, 'keys') else r[6]
            p3 = r['player3'] if isinstance(r, dict) or hasattr(r, 'keys') else r[7]
            s3 = r['score3'] if isinstance(r, dict) or hasattr(r, 'keys') else r[8]
            p4 = r['player4'] if isinstance(r, dict) or hasattr(r, 'keys') else r[9]
            s4 = r['score4'] if isinstance(r, dict) or hasattr(r, 'keys') else r[10]
            dt = r['date'] if isinstance(r, dict) or hasattr(r, 'keys') else r[1]

            p_scores = []
            if p1 and s1 is not None: p_scores.append((p1, float(s1)))
            if p2 and s2 is not None: p_scores.append((p2, float(s2)))
            if p3 and s3 is not None: p_scores.append((p3, float(s3)))
            if p4 and s4 is not None: p_scores.append((p4, float(s4)))
            if len(p_scores) < 2: continue

            s_num = None
            div = 'Premier'
            is_target = False

            if slug == 'international':
                m = re.search(r'International\s+S(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else ('Master' if s_num >= 28 else 'Premier')
                    if ('Master' in div or 'Grandmaster' in div or 'Diamond' in div or 'Premier' in div):
                        is_target = True
            elif slug == 'intermezzo':
                m = re.search(r'Intermezzo\s+S(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else 'Premier'
                    if ('Master' in div or 'Grandmaster' in div or 'Diamond' in div or 'Premier' in div):
                        is_target = True
            elif slug == 'royal_league':
                m = re.search(r'RL_s(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else 'Emperor'
                    if 'Emperor' in div or 'Premier' in div:
                        is_target = True

            if not is_target or s_num is None:
                continue

            season_key = f'Season {s_num}'
            awarded = assign_points(p_scores, p_count)
            for p, pts in awarded:
                c_key = (season_key, p)
                campaigns[c_key]['pts'] += pts
                campaigns[c_key]['games'] += 1
                campaigns[c_key]['div'] = div
                campaigns[c_key]['date'] = dt
                if (p_count == 4 and pts == 6.0) or (p_count == 3 and pts == 5.0) or (p_count == 2 and pts == 2.0):
                    campaigns[c_key]['wins'] += 1
                elif (p_count == 4 and pts == 3.0) or (p_count == 3 and pts == 2.0) or (p_count == 2 and pts == 1.0):
                    campaigns[c_key]['2nd'] += 1

        records = []
        min_games = 5 if slug == 'royal_league' else 6
        for (season_key, p), data in campaigns.items():
            if data['games'] >= min_games:
                records.append({
                    'player': p,
                    'season': season_key,
                    'division': data['div'],
                    'points': data['pts'],
                    'games': data['games'],
                    'wins': data['wins'],
                    'second_places': data['2nd'],
                    'date': data['date']
                })

        records.sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        return records[:limit]
    finally:
        conn.close()


@tournaments_bp.route('')
def index():
    """Tournaments Hub overview page."""
    series_map = get_populated_tournament_series()
    return render_template('tournaments/hub.html', series_list=list(series_map.values()))


@tournaments_bp.route('/<series_slug>')
def series_detail(series_slug):
    """Detailed showcase page for a specific tournament series."""
    series_map = get_populated_tournament_series()
    series = series_map.get(series_slug.lower())
    if not series:
        abort(404)
    records = get_tournament_records(series_slug.lower(), limit=10)
    seasonal_records = get_seasonal_points_records(series_slug.lower(), limit=10)
    return render_template(
        'tournaments/detail.html',
        series=series,
        all_series=list(series_map.values()),
        records=records,
        seasonal_records=seasonal_records
    )
