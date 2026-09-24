"""Unit tests for Tournament Season Completeness & Rule Engine."""
import pytest
from src.data.completeness import (
    calculate_expected_games_for_group,
    extract_division_name,
    evaluate_season_completeness,
    get_season_rule,
)

def test_calculate_expected_games_round_robin():
    # 8 players round-robin: 8 * 7 / 2 = 28
    assert calculate_expected_games_for_group(8, format_type='round_robin_2p') == 28
    # 7 players: 7 * 6 / 2 = 21
    assert calculate_expected_games_for_group(7, format_type='round_robin_2p') == 21
    # 6 players: 6 * 5 / 2 = 15
    assert calculate_expected_games_for_group(6, format_type='round_robin_2p') == 15
    # Less than 2 players
    assert calculate_expected_games_for_group(1, format_type='round_robin_2p') == 0
    # Fixed games override
    assert calculate_expected_games_for_group(8, fixed_games=10) == 10

def test_extract_division_name():
    assert extract_division_name("RL_s09 - Emperor - game 12") == "Emperor"
    assert extract_division_name("RL_s08 - Baron 1 game 14") == "Baron 1"
    assert extract_division_name("RL_s08 - Count 8 - game 28") == "Count 8"
    assert extract_division_name("RL_s07 - Knight 12 g 5") == "Knight 12"

def test_evaluate_season_completeness():
    # Construct a complete 3-player division (3*2/2 = 3 games)
    matches_complete = [
        {"tournament": "RL_s09 - Emperor - game 1", "participants": [("Alice", 200), ("Bob", 150)]},
        {"tournament": "RL_s09 - Emperor - game 2", "participants": [("Alice", 210), ("Charlie", 180)]},
        {"tournament": "RL_s09 - Emperor - game 3", "participants": [("Bob", 190), ("Charlie", 160)]},
    ]
    res = evaluate_season_completeness(matches_complete, "Royal League", 9)
    assert res["total_groups"] == 1
    assert res["completed_groups"] == 1
    assert res["is_complete"] is True
    assert res["completeness_pct"] == 100.0
    assert len(res["incomplete_groups"]) == 0

    # Incomplete division: only 2 games of 3 played
    matches_incomplete = matches_complete[:2]
    res_inc = evaluate_season_completeness(matches_incomplete, "Royal League", 9)
    assert res_inc["is_complete"] is False
    assert res_inc["completed_groups"] == 0
    assert len(res_inc["incomplete_groups"]) == 1
    assert res_inc["incomplete_groups"][0]["missing"] == 1

def test_get_season_rule_fallback_and_matching():
    rule = get_season_rule("Royal League", 9)
    assert rule["format"] == "round_robin_2p"
    assert rule.get("default_players_per_group") == 8
