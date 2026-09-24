"""Tests for tournament sources scanning and auto-registration."""
import pytest
from pathlib import Path
from src.scrapers.sources import (
    scan_tournament_sources,
    register_tournament_source,
    infer_tournament_folder_from_title
)

def test_scan_tournament_sources():
    sources = scan_tournament_sources()
    assert isinstance(sources, list)
    assert len(sources) > 0

    # Verify key known folders exist
    folders = [s["folder"] for s in sources]
    assert "Royal_League" in folders or "Australien_Open" in folders

def test_infer_tournament_folder():
    assert infer_tournament_folder_from_title("Through the Ages Royal League Season 2") == "Royal_League"
    assert infer_tournament_folder_from_title("International Championship Season 35") == "International_Championship"
    assert infer_tournament_folder_from_title("Aussie Open 2027") == "Australien_Open"
    assert infer_tournament_folder_from_title("Custom Cup 2026") == "Custom_Cup_2026"

def test_register_tournament_source(tmp_path):
    res = register_tournament_source(
        tournament_name="New_League_2026",
        source_url="https://account.czechgames.com/tournaments/detail/9999",
        result_csv_content="player,place,games\nAlice,1,5\nBob,2,5\n",
        tournaments_dir=tmp_path
    )
    assert res["success"] is True
    assert res["folder"] == "New_League_2026"
    
    target_folder = tmp_path / "New_League_2026"
    assert target_folder.exists()
    
    source_file = target_folder / "New_sources.md"
    assert source_file.exists()
    assert "https://account.czechgames.com/tournaments/detail/9999" in source_file.read_text(encoding="utf-8")
    
    result_file = target_folder / "result.csv"
    assert result_file.exists()
    assert "Alice,1,5" in result_file.read_text(encoding="utf-8")
