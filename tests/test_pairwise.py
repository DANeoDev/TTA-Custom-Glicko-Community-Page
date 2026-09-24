"""Tests for pairwise match decomposition and opponent statistics."""
import pytest
from src.data.db import get_connection

def test_direntropy_pairwise_counts():
    conn = get_connection()
    try:
        # Sum outcomes where DireNTropy is player_a in historical baseline
        row_a = conn.execute("""
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN outcome_a = 1.0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_a = 0.0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome_a = 0.5 THEN 1 ELSE 0 END) as draws
            FROM pairwise_matches
            WHERE player_a = 'DireNTropy'
        """).fetchone()

        # Sum outcomes where DireNTropy is player_b in historical baseline
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

        # In ratings_overall.csv: Opps=334 (baseline) or 344 (with 2026 matches)
        assert total_opps in (334, 344)
        assert total_wins in (261, 267)
        assert total_losses in (72, 76)
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
        assert counts[2] in (45384, 47219, 47270)
        assert counts[3] in (61733, 62714, 62751, 62752)
        assert counts[4] in (24307, 25055, 25380, 25522)
    finally:
        conn.close()
