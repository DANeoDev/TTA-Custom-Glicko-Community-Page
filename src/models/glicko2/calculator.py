"""Glicko-2 calendar monthly batch calculator calibrated to TTA tournament cadence."""
from collections import defaultdict
from datetime import datetime
import sqlite3
from typing import Dict, List, Tuple, Optional

from src.data.db import get_connection
from src.models.glicko2.engine import Rating, update_rating, GLICKO2_SCALE

# Calibrated constants matching official TTA online implementation
CALIBRATED_TAU = 0.3
CALIBRATED_SIGMA = 0.03
INACTIVITY_DRIFT_PER_MONTH = 0.01  # gentle variance growth per missed month (~1.7 RD)

def compute_glicko2_ratings(
    weighted: bool = False,
    player_count: int = 0,
    tau: float = CALIBRATED_TAU,
    db_path: Optional[str] = None
) -> Dict[str, Rating]:
    """Runs chronological monthly Glicko-2 updates for matches.
    
    player_count: 0 for all matches, or 2, 3, 4 for specific format.
    If weighted is False, computes 'glicko2_std' (matches official online leaderboard).
    If weighted is True, computes 'glicko2_mp' (fractional w=1/(N-1) variance-calibrated).
    """
    model_type = 'glicko2_mp' if weighted else 'glicko2_std'
    conn = get_connection(db_path)

    try:
        if player_count and player_count > 0:
            rows = conn.execute("""
                SELECT date, tournament, player_a, player_b, outcome_a, weight
                FROM pairwise_matches
                WHERE player_count = ?
                ORDER BY date, pairwise_id
            """, (player_count,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT date, tournament, player_a, player_b, outcome_a, weight
                FROM pairwise_matches
                ORDER BY date, pairwise_id
            """).fetchall()

        # Group matches by calendar month (YYYY-MM)
        periods = defaultdict(list)
        period_dates = {}
        for r in rows:
            m_key = r['date'][:7]
            periods[m_key].append(r)
            period_dates[m_key] = r['date'][:10]

        ratings: Dict[str, Rating] = defaultdict(lambda: Rating(1500.0, 350.0, CALIBRATED_SIGMA))
        history_records = []

        sorted_months = sorted(periods.keys())

        for m_key in sorted_months:
            period_matches = periods[m_key]
            period_date_str = period_dates[m_key]

            # Collect matches per player in this month
            player_encounters = defaultdict(list)
            for m in period_matches:
                pa, pb = m['player_a'], m['player_b']
                out_a, w = m['outcome_a'], m['weight']
                player_encounters[pa].append((ratings[pb], out_a, w))
                player_encounters[pb].append((ratings[pa], 1.0 - out_a, w))

            active_players = set(player_encounters.keys())

            # Update active players
            for p_name, encounters in player_encounters.items():
                ratings[p_name] = update_rating(
                    ratings[p_name],
                    encounters,
                    tau=tau,
                    weighted=weighted
                )
                curr = ratings[p_name]
                history_records.append((
                    model_type, player_count, p_name, period_date_str,
                    round(curr.rating, 2), round(curr.rd, 2), round(curr.conservative_rating, 2)
                ))

            # Apply mild inactivity drift to already-active players who missed this month
            for p_name in list(ratings.keys()):
                if p_name not in active_players and ratings[p_name].rd < 350.0:
                    r_cur = ratings[p_name]
                    phi_new = (r_cur.phi**2 + INACTIVITY_DRIFT_PER_MONTH**2)**0.5
                    new_rd = min(350.0, phi_new * GLICKO2_SCALE)
                    ratings[p_name] = Rating(r_cur.rating, new_rd, r_cur.sigma)

        # Aggregate player statistics for this format
        if player_count and player_count > 0:
            stats_rows = conn.execute("""
                SELECT 
                    p.name,
                    COUNT(pm.pairwise_id) as opps_count,
                    SUM(CASE WHEN pm.player_a = p.name AND pm.outcome_a = 1.0 THEN 1
                             WHEN pm.player_b = p.name AND pm.outcome_a = 0.0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pm.player_a = p.name AND pm.outcome_a = 0.0 THEN 1
                             WHEN pm.player_b = p.name AND pm.outcome_a = 1.0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pm.outcome_a = 0.5 THEN 1 ELSE 0 END) as draws,
                    MAX(pm.date) as last_played
                FROM players p
                INNER JOIN pairwise_matches pm ON (p.name = pm.player_a OR p.name = pm.player_b) AND pm.player_count = ?
                GROUP BY p.name
            """, (player_count,)).fetchall()
        else:
            stats_rows = conn.execute("""
                SELECT 
                    p.name,
                    COUNT(pm.pairwise_id) as opps_count,
                    SUM(CASE WHEN pm.player_a = p.name AND pm.outcome_a = 1.0 THEN 1
                             WHEN pm.player_b = p.name AND pm.outcome_a = 0.0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pm.player_a = p.name AND pm.outcome_a = 0.0 THEN 1
                             WHEN pm.player_b = p.name AND pm.outcome_a = 1.0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pm.outcome_a = 0.5 THEN 1 ELSE 0 END) as draws,
                    MAX(pm.date) as last_played
                FROM players p
                LEFT JOIN pairwise_matches pm ON p.name = pm.player_a OR p.name = pm.player_b
                GROUP BY p.name
            """).fetchall()
        player_stats = {r['name']: r for r in stats_rows}

        # Rank players by conservative rating C = rating - 3*rd
        player_rankings = []
        for p_name, r_obj in ratings.items():
            st = player_stats.get(p_name)
            opps = st['opps_count'] if st else 0
            if player_count and player_count > 0 and opps == 0:
                continue
            w_cnt = st['wins'] if st else 0
            l_cnt = st['losses'] if st else 0
            d_cnt = st['draws'] if st else 0
            wr = round((w_cnt + 0.5 * d_cnt) / max(1, opps) * 100.0, 2)
            lp = st['last_played'] if st else None

            player_rankings.append({
                'name': p_name,
                'rating': round(r_obj.rating, 2),
                'rd': round(r_obj.rd, 2),
                'sigma': round(r_obj.sigma, 4),
                'c_rating': round(r_obj.conservative_rating, 2),
                'opps': opps,
                'wins': w_cnt,
                'losses': l_cnt,
                'draws': d_cnt,
                'win_rate': wr,
                'last_played': lp
            })

        player_rankings.sort(key=lambda x: x['c_rating'], reverse=True)

        rating_rows = []
        for rank, p_data in enumerate(player_rankings, 1):
            rating_rows.append((
                model_type, player_count, p_data['name'], p_data['rating'], p_data['rd'],
                p_data['sigma'], p_data['c_rating'], rank, 0,
                p_data['opps'], p_data['opps'], p_data['wins'], p_data['losses'],
                p_data['draws'], p_data['win_rate'], p_data['last_played']
            ))

        with conn:
            conn.execute('DELETE FROM player_ratings WHERE model_type = ? AND player_count = ?;', (model_type, player_count))
            conn.execute('DELETE FROM rating_history WHERE model_type = ? AND player_count = ?;', (model_type, player_count))

            conn.executemany("""
                INSERT INTO player_ratings (
                    model_type, player_count, player_name, rating, rd, sigma, c_rating, rank, rank_delta,
                    games_played, opponents_count, wins, losses, draws, win_rate, last_played
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rating_rows)

            conn.executemany("""
                INSERT INTO rating_history (
                    model_type, player_count, player_name, period_date, rating, rd, c_rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, history_records)

        fmt_label = f"{player_count}p" if player_count > 0 else "All"
        print(f"Successfully saved {len(rating_rows)} ratings and {len(history_records)} history points for {model_type} ({fmt_label}).")
        return ratings

    finally:
        conn.close()
