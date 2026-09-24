"""Season Completeness and Tournament Rule Engine for TTA tournaments."""
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RULES_FILE = Path(__file__).resolve().parents[2] / "data" / "tournaments" / "tournament_rules.json"

DEFAULT_RULES = {
    "Royal League": {
        "default_format": "round_robin_2p",
        "rules": [
            {
                "from_season": 1,
                "to_season": None,
                "format": "round_robin_2p",
                "default_players_per_group": 8,
                "games_per_group": 28,
                "description": "Standard 2-player round-robin divisions (8 players = 28 games)."
            }
        ]
    }
}


def load_tournament_rules() -> Dict[str, Any]:
    """Loads tournament rule configurations."""
    if RULES_FILE.exists():
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read {RULES_FILE}: {e}")
    return DEFAULT_RULES


def get_season_rule(tournament_name: str, season_num: Optional[int] = None) -> Dict[str, Any]:
    """Finds the active rule definition for a tournament and specific season."""
    all_rules = load_tournament_rules()
    # Normalise: underscores and spaces are interchangeable in lookup
    t_norm = tournament_name.replace("_", " ").lower().strip()
    t_key = tournament_name
    if t_key not in all_rules:
        for k in all_rules:
            k_norm = k.replace("_", " ").lower()
            if k_norm in t_norm or t_norm in k_norm:
                t_key = k
                break

    t_config = all_rules.get(t_key, {})
    rules_list = t_config.get("rules", [])
    if not rules_list:
        return {"format": t_config.get("default_format", "round_robin_2p")}
    if season_num is None:
        return rules_list[-1]
    for r in rules_list:
        f_s = r.get("from_season", 1)
        t_s = r.get("to_season")
        if f_s <= season_num and (t_s is None or season_num <= t_s):
            return r
    return rules_list[-1]


def extract_division_name(tournament_str: str) -> str:
    """Extracts the division/group name from a tournament match string."""
    m = re.search(r'(?:RL_s\d+|[A-Za-z0-9_]+)\s*-\s*(.*?)(?:\s*(?:-|game|\bg\b)\s*\d+|$)', tournament_str, re.IGNORECASE)
    if m and m.group(1).strip():
        div = m.group(1).strip()
        div = re.sub(r'[\s\-]+$', '', div)
        return div
    return "Main"


def calculate_expected_games_for_group(
    player_count: int,
    format_type: str = "round_robin_2p",
    fixed_games: Optional[int] = None
) -> int:
    """Computes expected games count for a group based on player count and format."""
    if fixed_games is not None:
        return fixed_games
    if format_type == "round_robin_2p":
        if player_count < 2:
            return 0
        return (player_count * (player_count - 1)) // 2
    return 0


def evaluate_season_completeness(
    matches: List[Dict[str, Any]],
    tournament_name: str,
    season_num: Optional[int] = None
) -> Dict[str, Any]:
    """Evaluates completeness of season matches against tournament group rules."""
    rule = get_season_rule(tournament_name, season_num)
    fmt = rule.get("format", "round_robin_2p")
    fixed_games_rule = rule.get("games_per_group")

    group_games: Dict[str, int] = {}
    group_players: Dict[str, set] = {}

    for m in matches:
        t_str = m.get("tournament", "")
        div = extract_division_name(t_str)
        group_games[div] = group_games.get(div, 0) + 1
        
        if div not in group_players:
            group_players[div] = set()
            
        parts = m.get("participants", [])
        for p in parts:
            if isinstance(p, (list, tuple)) and len(p) >= 1:
                group_players[div].add(p[0])
            elif isinstance(p, str):
                group_players[div].add(p)

    total_groups = len(group_games)
    completed_groups = 0
    total_expected = 0
    total_actual = 0
    groups_detail = {}
    incomplete_groups = []

    for div, act_count in sorted(group_games.items()):
        p_count = len(group_players.get(div, set()))
        eff_player_count = p_count
        if eff_player_count < 2 and rule.get("default_players_per_group"):
            eff_player_count = rule.get("default_players_per_group")
            
        exp_count = calculate_expected_games_for_group(eff_player_count, fmt, fixed_games_rule)
        if exp_count == 0 and act_count > 0:
            exp_count = act_count
            
        is_grp_complete = act_count >= exp_count
        if is_grp_complete:
            completed_groups += 1
        else:
            incomplete_groups.append({
                "division": div,
                "actual": act_count,
                "expected": exp_count,
                "missing": exp_count - act_count,
                "players_count": p_count
            })
            
        total_actual += act_count
        total_expected += exp_count
        
        groups_detail[div] = {
            "actual": act_count,
            "expected": exp_count,
            "players_count": p_count,
            "is_complete": is_grp_complete,
            "missing": max(0, exp_count - act_count)
        }

    pct = round((total_actual / total_expected * 100.0), 1) if total_expected > 0 else 100.0
    is_complete = (completed_groups == total_groups and total_groups > 0 and total_actual >= total_expected)

    if is_complete:
        summary = f"{completed_groups}/{total_groups} groups complete ({total_actual}/{total_expected} games - 100%)"
    else:
        missing_total = max(0, total_expected - total_actual)
        summary = f"{completed_groups}/{total_groups} groups complete ({total_actual}/{total_expected} games - {pct}%, {missing_total} pending)"

    return {
        "tournament_name": tournament_name,
        "season_num": season_num,
        "total_groups": total_groups,
        "completed_groups": completed_groups,
        "total_expected_games": total_expected,
        "total_actual_games": total_actual,
        "completeness_pct": pct,
        "is_complete": is_complete,
        "summary": summary,
        "groups_detail": groups_detail,
        "incomplete_groups": incomplete_groups,
        "rule_applied": rule
    }


def build_player_game_matrix(
    group_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Builds a per-player opponent matrix for a single division's match rows.

    Each row in group_rows must have 'participants': [(player_name, score), ...].

    Returns a dict with:
      - players: sorted list of player names
      - played: set of frozensets {a, b} for each completed pairing
      - missing: list of (player_a, player_b) tuples for absent pairings
      - appearances: {player: int} count of games per player
      - complete: bool
    """
    players: set = set()
    played: set = set()

    for row in group_rows:
        parts = row.get("participants", [])
        names = []
        for p in parts:
            if isinstance(p, (list, tuple)) and len(p) >= 1:
                names.append(p[0].strip())
            elif isinstance(p, str):
                names.append(p.strip())
        for name in names:
            players.add(name)
        # In a 2-player game the first two participants are the pair
        if len(names) >= 2:
            played.add(frozenset([names[0], names[1]]))

    sorted_players = sorted(players)
    n = len(sorted_players)

    # Determine all expected pairings
    missing_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pair = frozenset([sorted_players[i], sorted_players[j]])
            if pair not in played:
                missing_pairs.append((sorted_players[i], sorted_players[j]))

    appearances = {p: 0 for p in sorted_players}
    for pair in played:
        pair_list = list(pair)
        if pair_list[0] in appearances:
            appearances[pair_list[0]] += 1
        if len(pair_list) > 1 and pair_list[1] in appearances:
            appearances[pair_list[1]] += 1

    expected_games = n * (n - 1) // 2 if n >= 2 else 0

    return {
        "players": sorted_players,
        "player_count": n,
        "expected_games": expected_games,
        "played_games": len(played),
        "missing_pairs": missing_pairs,
        "missing_count": len(missing_pairs),
        "appearances": appearances,
        "complete": len(missing_pairs) == 0 and expected_games > 0,
    }


def check_group_completeness(
    matches: List[Dict[str, Any]],
    tournament_name: str,
    season_num: Optional[int] = None,
) -> Dict[str, Any]:
    """Per-group completeness check using the player game matrix.

    Groups matches by division, builds a matrix per group, returns per-group
    missing pair lists so the UI can show exactly which games are absent.
    """
    group_rows: Dict[str, List[Dict[str, Any]]] = {}
    for m in matches:
        div = extract_division_name(m.get("tournament", ""))
        if div not in group_rows:
            group_rows[div] = []
        group_rows[div].append(m)

    groups_out = {}
    total_missing = 0
    incomplete_groups = []

    for div, rows in sorted(group_rows.items()):
        matrix = build_player_game_matrix(rows)
        groups_out[div] = matrix
        if not matrix["complete"]:
            total_missing += matrix["missing_count"]
            incomplete_groups.append({
                "division": div,
                "player_count": matrix["player_count"],
                "expected": matrix["expected_games"],
                "actual": matrix["played_games"],
                "missing": matrix["missing_count"],
                "missing_pairs": matrix["missing_pairs"],
            })

    is_complete = total_missing == 0 and len(groups_out) > 0
    return {
        "tournament_name": tournament_name,
        "season_num": season_num,
        "total_groups": len(groups_out),
        "incomplete_groups": incomplete_groups,
        "total_missing_games": total_missing,
        "is_complete": is_complete,
        "groups": groups_out,
    }

