"""Tests for WHR solver and engine convergence."""
import numpy as np
import pytest
from src.models.whr.solver import solve_tridiagonal
from src.models.whr.engine import WHREngine

def test_thomas_solver_identity():
    # 3x3 diagonal system
    diag = np.array([2.0, 2.0, 2.0])
    off = np.array([-1.0, -1.0])
    rhs = np.array([1.0, 0.0, 1.0])

    # A = [[2, -1, 0], [-1, 2, -1], [0, -1, 2]]
    # A * [1, 1, 1] = [1, 0, 1] -> solution should be [1, 1, 1]
    sol = solve_tridiagonal(diag, off, rhs)
    np.testing.assert_allclose(sol, [1.0, 1.0, 1.0], atol=1e-5)

def test_whr_two_player_synthetic():
    whr = WHREngine(w2_per_day=0.01)
    
    # Day 1: Player A beats Player B
    whr.add_game('2023-01-01', 'Alice', 'Bob', 1.0)
    # Day 2: Player A beats Player B again
    whr.add_game('2023-01-02', 'Alice', 'Bob', 1.0)
    # Day 3: Player A beats Player B again
    whr.add_game('2023-01-03', 'Alice', 'Bob', 1.0)

    whr.fit(max_iter=10, tol=1e-3)

    alice_r, alice_rd = whr.get_current_rating('Alice')
    bob_r, bob_rd = whr.get_current_rating('Bob')

    # Alice won 3 games in a row -> Alice rating must be > 1500, Bob < 1500
    assert alice_r > 1500.0
    assert bob_r < 1500.0
    assert alice_r > bob_r
