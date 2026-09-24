"""Tests for safe append-only merger, deduplication, and historical immutability."""
import csv
import pytest
from pathlib import Path
from src.data.merger import (
    make_dedup_key, preview_scraped_matches,
    commit_new_matches, create_safety_backup
)

def test_make_dedup_key_invariance():
    # Same match with different participant ordering must yield identical keys
    parts_a = [("Alice", 200.0), ("Bob", 180.0)]
    parts_b = [("Bob", 180.0), ("Alice", 200.0)]

    key_a = make_dedup_key("International S10", "2026-05-01", parts_a)
    key_b = make_dedup_key("International S10", "2026-05-01", parts_b)
    assert key_a == key_b

def test_preview_and_commit_append_only(tmp_path):
    # 1. Create a dummy initial matches CSV
    dummy_csv = tmp_path / "all_matches.csv"
    with open(dummy_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Tournament", "Date",
            "Player1", "Score1",
            "Player2", "Score2",
            "Player3", "Score3",
            "Player4", "Score4",
            "Player_Count"
        ])
        writer.writerow([
            "Test Tourney", "2026-01-01",
            "PlayerA", 200, "PlayerB", 150, "", "", "", "", 2
        ])

    initial_content = dummy_csv.read_text(encoding="utf-8")

    # 2. Test candidate games: 1 duplicate, 1 brand new
    candidate_games = [
        # Duplicate game
        {
            "tournament": "Test Tourney",
            "date": "2026-01-01",
            "participants": [("PlayerA", 200.0), ("PlayerB", 150.0)]
        },
        # Brand new game
        {
            "tournament": "Test Tourney",
            "date": "2026-01-02",
            "participants": [("PlayerC", 220.0), ("PlayerD", 190.0), ("PlayerE", 140.0)]
        }
    ]

    diff = preview_scraped_matches(candidate_games, csv_path=dummy_csv)
    assert diff["total_scraped"] == 2
    assert diff["duplicate_count"] == 1
    assert diff["new_matches_count"] == 1
    assert diff["new_matches"][0]["tournament"] == "Test Tourney"
    assert diff["new_matches"][0]["player_count"] == 3

    # 3. Test commit without DB (file only)
    res = commit_new_matches(
        diff["new_matches"],
        csv_path=dummy_csv,
        create_backup=False,
        commit_to_db=False,
        tournaments_dir=tmp_path,
        export_snapshot=False
    )
    assert res["status"] == "success"
    assert res["rows_appended"] == 1


    # 4. Verify historical immutability: initial row is untouched, new row is at bottom
    updated_content = dummy_csv.read_text(encoding="utf-8")
    assert updated_content.startswith(initial_content)
    assert "PlayerC,220.0,PlayerD,190.0,PlayerE,140.0" in updated_content

def test_save_season_matches_to_tournament_folder(tmp_path):
    from src.data.merger import save_season_matches_to_tournament_folder
    matches = [
        {"tournament": "RL_s09 - Emperor - game 1", "date": "2026-06-01", "participants": [("Alice", 200.0), ("Bob", 150.0)]},
        {"tournament": "RL_s09 - Emperor - game 2", "date": "2026-06-01", "participants": [("Charlie", 190.0), ("David", 140.0)]},
    ]
    res = save_season_matches_to_tournament_folder(matches, tournaments_dir=tmp_path)
    assert len(res) == 1
    assert res[0]["folder"] == "Royal_League"
    assert res[0]["season"] == 9
    assert res[0]["rows_written"] == 2

    # Verify CSV content in new matches/ subfolder with CODE_sNN naming
    season_csv = tmp_path / "Royal_League" / "matches" / "RL_s09.csv"
    assert season_csv.exists()
    content = season_csv.read_text(encoding="utf-8")
    assert "Tournament,Date,Player1,Score1" in content
    assert "RL_s09 - Emperor - game 1" in content
    assert "RL_s09 - Emperor - game 2" in content


def test_humanize_tournament_stage():
    from src.data.merger import humanize_tournament_stage

    cases = {
        "French Open 2026 (Even Games) Stage 1 - group 1 game 1": "French Open 2026 Stage 1 (even games)",
        "French Open 2026 (Odd Games) Stage 1 - group 1 game 1": "French Open 2026 Stage 1 (odd games)",
        "International S34 - Group A - game 1": "International Championship Season 34 (CGE 25)",
        "Mercurial Season 35 - Tier 1 - game 1": "Mercurial Ladder Season 35",
        "Mercurial Season 36 - Tier 2 - game 1": "Mercurial Ladder Season 36",
        "RL_s09 - Emperor - game 1": "Royal League Season 9",
        "Slow Burn S15 - game 2": "Slow Burn First Edition Season 15",
        "Sodium Season 14 - Tier 1 - game 1": "Sodium Ladder Season 14",
        "Sodium Season 15 - Tier 1 - game 1": "Sodium Ladder Season 15",
        "Survivors Cup 2026 Stage 7 - group 1 game 1": "Survivors Cup 2026 Stage 7",
        "Survivors Cup 2026 Stage 8 - group 1 game 1": "Survivors Cup 2026 Stage 8",
        "Survivors Cup 2026 Stage 9 - group 1 game 1": "Survivors Cup 2026 Stage 9",
        "Survivors Cup 2026 Stage 10 - group 1 game 1": "Survivors Cup 2026 Stage 10",
        "Survivors Cup 2026 Stage 11 - group 1 game 1": "Survivors Cup 2026 Stage 11",
        "TCL Round 138": "Transcontinental Ladder Round 138 (CGE 84)",
        "TCL Round 139": "Transcontinental Ladder Round 139 (CGE 85)",
        "World Championship 2026 Stage 5 - game 1": "World Championship 2026 Stage 5",
        "World Championship 2026 Stage 6 - game 1": "World Championship 2026 Stage 6",
    }

    for raw, expected in cases.items():
        assert humanize_tournament_stage(raw) == expected


def test_resolve_multi_stage_tournaments():
    from src.data.merger import resolve_tournament_folder_and_season

    assert resolve_tournament_folder_and_season("Survivors Cup 2026 Stage 7 - game 1") == ("Survivors_Cup_2026", 7, "SC")
    assert resolve_tournament_folder_and_season("French Open 2026 (Even Games) Stage 1 - game 1") == ("French_Open_Even", 1, "FO_even")
    assert resolve_tournament_folder_and_season("French Open 2026 (Odd Games) Stage 1 - game 1") == ("French_Open_Odd", 1, "FO_odd")
    assert resolve_tournament_folder_and_season("World Championship 2026 Stage 5 - game 1") == ("World_Championship_2026", 5, "WC")
    assert resolve_tournament_folder_and_season("Slow Burn Season 15 - game 1") == ("Slow_Burn_First_Edition", 15, "SB")
    assert resolve_tournament_folder_and_season("Slow Burn Second Edition Season 1 - game 1") == ("Slow_Burn_Second_Edition", 1, "SB")
    assert resolve_tournament_folder_and_season("Mercurial Ladder Season 35 - game 1") == ("Mercurial_Ladder", 35, "ML")


def test_resolve_folder_and_season_sodium_and_ic_isolation():
    from src.data.merger import resolve_tournament_folder_and_season, humanize_tournament_stage

    # 1. Arsenic 2 must NEVER resolve to International Championship
    s1 = "Sodium Ladder         - season 14 Season 14 - Sodium Ladder 33-Arsenic 2 game 1"
    folder, season, code = resolve_tournament_folder_and_season(s1)
    assert folder == "Sodium_Ladder"
    assert season == 14
    assert code == "SL"
    assert humanize_tournament_stage(s1) == "Sodium Ladder Season 14"

    # 2. Season 16 with Arsenic 2
    s2 = "Sodium Ladder Season 16 - Sodium Ladder 33-Arsenic 2 game 1"
    folder, season, code = resolve_tournament_folder_and_season(s2)
    assert folder == "Sodium_Ladder"
    assert season == 16
    assert code == "SL"
    assert humanize_tournament_stage(s2) == "Sodium Ladder Season 16"

    # 3. Chemical element atomic numbers (e.g. 28-Nickel) must NOT be parsed as season numbers
    s3 = "Sodium Ladder - Sodium Ladder 28-Nickel game 1"
    folder, season, code = resolve_tournament_folder_and_season(s3)
    assert folder == "Sodium_Ladder"
    assert season is None  # NOT 28!
    assert code == "SL"

    # 4. Valid International Championship
    s4 = "International S34 - Group A - game 1"
    folder, season, code = resolve_tournament_folder_and_season(s4)
    assert folder == "International_Championship"
    assert season == 34
    assert code == "IC"


def test_append_matches_rejects_pre_2026(tmp_path):
    from src.data.merger import commit_new_matches
    dummy_csv = tmp_path / "all_matches.csv"
    
    old_matches = [
        {"tournament": "French Open 2025", "date": "2025-07-08", "participants": [("Alice", 200.0), ("Bob", 150.0)]}
    ]
    res = commit_new_matches(old_matches, csv_path=dummy_csv, commit_to_db=False, create_backup=False)
    assert res["status"] == "skipped"
    assert "cutoff" in res["message"]
    assert not dummy_csv.exists()



