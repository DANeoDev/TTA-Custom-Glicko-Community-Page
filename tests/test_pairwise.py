"""Tests for pairwise match decomposition and opponent statistics."""
import pytest
from src.data.db import get_connection

def test_direntropy_pairwise_counts():
    conn = get_connection()
    try:
        # Sum outcomes where DireNTropy is player_a
        row_a = conn.execute("""
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws
            FROM pairwise_matches
            WHERE player_a = 'DireNTropy'
        """).fetchone()

        # Sum outcomes where DireNTropy is player_b
        row_b = conn.execute("""
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws
            FROM pairwise_matches
            WHERE player_b = 'DireNTropy'
        """).fetchone()

        total_opps = (row_a['games'] or 0) + (row_b['games'] or 0)
        total_wins = (row_a['wins'] or 0) + (row_b['wins'] or 0)
        total_losses = (row_a['losses'] or 0) + (row_b['losses'] or 0)
        total_draws = (row_a['draws'] or 0) + (row_b['draws'] or 0)

        # In ratings_overall.csv: Opps=334, Ws=261, Ls=72, Ds=1
        assert total_opps == 334
        assert total_wins == 261
        assert total_losses == 72
        assert total_draws == 1

    finally:
        conn.close()

def test_player_count_distribution():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT player_count, COUNT(*) as count
            FROM matches
            GROUP BY player_count
            ORDER BY player_count
        """).fetchall()
        counts = {r['player_count']: r['count'] for r in rows}
        assert counts[2] == 45384
        assert counts[3] == 61733
        assert counts[4] == 24307
    finally:
        conn.close()
