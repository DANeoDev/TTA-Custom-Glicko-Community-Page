"""Tests for CGE tournament scraper and DOM parsing logic."""
import pytest
from src.scrapers.cge import CGEClient

SAMPLE_CGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Royal League - Season 1 | CGE Online</title>
</head>
<body>
    <div class="container">
        <h1>Royal League - Season 1</h1>
        <div class="dates">Finished: 2026-05-27</div>
        
        <table class="table games-table">
            <thead>
                <tr>
                    <th>Game</th>
                    <th>Players & Scores</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Game #1</td>
                    <td>
                        <a href="/users/detail/101">vanishadow</a> 245,
                        <a href="/users/detail/102">Weidenbaum</a> 210,
                        <a href="/users/detail/103">Martin_Pecheur</a> 195,
                        <a href="/users/detail/104">Airren</a> 180
                    </td>
                </tr>
                <tr>
                    <td>Game #2</td>
                    <td>
                        <a href="/users/detail/105">DANeo</a> 230,
                        <a href="/users/detail/106">ben0728</a> 215,
                        <a href="/users/detail/107">Eske</a> 170
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def test_parse_tournament_html_title_and_games():
    parsed = CGEClient.parse_tournament_html(SAMPLE_CGE_HTML, tournament_id=5000)
    assert parsed["title"] == "Royal League - Season 1"
    assert parsed["tournament_id"] == 5000
    assert len(parsed["games"]) == 2

    # Game 1: 4 players, sorted descending
    g1 = parsed["games"][0]
    assert g1["player_count"] == 4
    assert g1["participants"][0] == ("vanishadow", 245.0)
    assert g1["participants"][1] == ("Weidenbaum", 210.0)
    assert g1["participants"][2] == ("Martin_Pecheur", 195.0)
    assert g1["participants"][3] == ("Airren", 180.0)

    # Game 2: 3 players
    g2 = parsed["games"][1]
    assert g2["player_count"] == 3
    assert g2["participants"][0] == ("DANeo", 230.0)
    assert g2["participants"][1] == ("ben0728", 215.0)
    assert g2["participants"][2] == ("Eske", 170.0)

def test_cge_client_init_and_delays():
    client = CGEClient(min_delay=1.0, max_delay=2.0)
    assert client.min_delay == 1.0
    assert client.max_delay == 2.0
    assert client.is_authenticated is False


SAMPLE_POPOVER_HTML = """
<table class="table tournaments-games">
  <tr>
    <td><span class="session-name-title">Royal League Emperor game 16</span></td>
  </tr>
  <tr>
    <td>
      <a class="player-tooltip">1. DANeo</a>
      <div id="popover-user2-1">
        <div>
          <div class="player-tooltip-result">1. DANeo ( 213 ) ,</div>
          <div class="player-tooltip-result">2. Raffaello ( 206 )</div>
        </div>
        <div>---</div>
        <div>
          <div class="player-tooltip-result">1. DANeo ( 146 ) ,</div>
          <div class="player-tooltip-result">2. Grozz ( 103 )</div>
        </div>
      </div>
      <a class="player-tooltip">2. Grozz</a>
    </td>
  </tr>
</table>
"""

def test_parse_popover_unique_opponent():
    parsed = CGEClient.parse_tournament_html(SAMPLE_POPOVER_HTML, target="5000/9")
    assert len(parsed["games"]) == 1
    g = parsed["games"][0]
    # Must match Grozz (146 vs 103), NOT the first history block against Raffaello!
    assert g["participants"][0] == ("DANeo", 146.0)
    assert g["participants"][1] == ("Grozz", 103.0)


def test_format_tournament_match_name_multistage():
    from src.scrapers.cge import format_tournament_match_name

    # Survivors Cup with stage_name
    assert format_tournament_match_name(
        "Survivors Cup 2026", 7, "group 1 game 1", stage_name="Stage 7"
    ) == "Survivors Cup 2026 Stage 7 - group 1 game 1"

    # French Open with (even games)
    assert format_tournament_match_name(
        "French Open 2026", 1, "group 1 game 1", stage_name="Stage 1 (even games)"
    ) == "French Open 2026 Stage 1 (even games) - group 1 game 1"

    # World Championship
    assert format_tournament_match_name(
        "World Championship 2026", 5, "game 1", stage_name="Stage 5"
    ) == "World Championship 2026 Stage 5 - game 1"

    # Transcontinental Ladder
    assert format_tournament_match_name(
        "Transcontinental Ladder", 138, "game 1", stage_name="Round 138"
    ) == "TCL Round 138 - game 1"


def test_crawl_tournament_all_stages_discovery(monkeypatch):
    sample_multistage_html = """
    <html>
    <head><title>Survivors Cup 2026 | CGE Online</title></head>
    <body>
      <div class="dropdown-menu">
        <a href="/tournaments/detail/1234/7">Stage 7</a>
        <a href="/tournaments/detail/1234/8">Stage 8</a>
      </div>
      <button id="dropdownMenuLink">Stage 8</button>
      <table class="tournaments-games"></table>
    </body>
    </html>
    """
    client = CGEClient()
    monkeypatch.setattr(client, "fetch_tournament_html", lambda target, force_refresh=False: sample_multistage_html)
    
    # Mock crawl_season_all_groups
    def mock_crawl(target, force_refresh=False):
        stage_num = target.split('/')[-1]
        return {
            "title": "Survivors Cup 2026",
            "active_season_num": int(stage_num),
            "games": [
                {
                    "tournament": f"Survivors Cup 2026 Stage {stage_num} - game 1",
                    "date": "2026-06-01",
                    "player_count": 2,
                    "participants": [("PlayerA", 200.0), ("PlayerB", 150.0)],
                    "raw_row": f"Survivors Cup 2026 Stage {stage_num} game 1"
                }
            ],
            "group_completeness": []
        }
    monkeypatch.setattr(client, "crawl_season_all_groups", mock_crawl)

    res = client.crawl_tournament_all_stages("1234")
    assert len(res["stages_summary"]) == 2
    assert res["games_count"] == 2
    tourney_names = {g["tournament"] for g in res["games"]}
    assert "Survivors Cup 2026 Stage 7 - game 1" in tourney_names
    assert "Survivors Cup 2026 Stage 8 - game 1" in tourney_names


def test_parse_player_result_item():
    from src.scrapers.cge import parse_player_result_item

    # Normal finished player
    p1 = parse_player_result_item("1. pv4 215")
    assert p1 == {"name": "pv4", "status": "finished", "score": 215.0, "rank": 1}

    p2 = parse_player_result_item("2. Grozz ( 208.5 )")
    assert p2 == {"name": "Grozz", "status": "finished", "score": 208.5, "rank": 2}

    # Resigned player
    p3 = parse_player_result_item("wolvs RESIGNED")
    assert p3 == {"name": "wolvs", "status": "resigned", "score": None, "rank": None}

    p4 = parse_player_result_item("3. Cresspahl ( RESIGNED )")
    assert p4 == {"name": "Cresspahl", "status": "resigned", "score": None, "rank": 3}

    # Timed out player
    p5 = parse_player_result_item("Vovka TIMED OUT")
    assert p5 == {"name": "Vovka", "status": "timeout", "score": None, "rank": None}

    p6 = parse_player_result_item("4. Vovka ( TIMED OUT )")
    assert p6 == {"name": "Vovka", "status": "timeout", "score": None, "rank": 4}

    # Invalid / empty
    assert parse_player_result_item("") is None
    assert parse_player_result_item("Players : 4") is None


def test_order_and_score_participants_hierarchy():
    from src.scrapers.cge import parse_player_result_item, order_and_score_participants

    # Worlds 2026 Stage 6 Lower 7 game 11 test case: 3 finished, 1 timeout
    candidates_worlds = [
        parse_player_result_item("1. pv4 215"),
        parse_player_result_item("2. Grozz 208"),
        parse_player_result_item("3. maximpodg 178"),
        parse_player_result_item("Vovka TIMED OUT"),
    ]
    res_worlds = order_and_score_participants(candidates_worlds)
    assert res_worlds == [
        ("pv4", 215.0),
        ("Grozz", 208.0),
        ("maximpodg", 178.0),
        ("Vovka", -5.0),
    ]

    # Test case: 1 finished, 2 resigns (2nd place resign gets -2.0, 3rd place resign gets -3.0)
    candidates_resigns = [
        parse_player_result_item("1. Martin_Pecheur 87"),
        parse_player_result_item("2. wolvs RESIGNED"),
        parse_player_result_item("3. totsilence RESIGNED"),
    ]
    res_resigns = order_and_score_participants(candidates_resigns)
    assert res_resigns == [
        ("Martin_Pecheur", 87.0),
        ("wolvs", -2.0),
        ("totsilence", -3.0),
    ]

    # Test case: finished + resigned + timeout
    # Resigned player is placed ahead of timeout player; timeout gets -5.0, resigned gets -3.0 in 4P
    candidates_mixed = [
        parse_player_result_item("1. PlayerA 250"),
        parse_player_result_item("2. PlayerB 200"),
        parse_player_result_item("PlayerC RESIGNED"),
        parse_player_result_item("PlayerD TIMED OUT"),
    ]
    res_mixed = order_and_score_participants(candidates_mixed)
    assert res_mixed == [
        ("PlayerA", 250.0),
        ("PlayerB", 200.0),
        ("PlayerC", -3.0),
        ("PlayerD", -5.0),
    ]


def test_parse_tournament_html_with_timeout_and_resigns():
    sample_html = """
    <table class="table tournaments-games">
      <tr>
        <td><span class="session-name-title">Worlds 2026 Lower 7 game 11</span></td>
      </tr>
      <tr>
        <td>
          <div>1. pv4 215</div>
          <div>2. Grozz 208</div>
          <div>3. maximpodg 178</div>
          <div><a class="player-tooltip">Vovka</a><br><span class="tournament-order-text-expired">TIMED OUT</span></div>
        </td>
      </tr>
    </table>
    """
    parsed = CGEClient.parse_tournament_html(sample_html, target="5633/6/41259")
    assert len(parsed["games"]) == 1
    g = parsed["games"][0]
    assert g["player_count"] == 4
    assert g["participants"] == [
        ("pv4", 215.0),
        ("Grozz", 208.0),
        ("maximpodg", 178.0),
        ("Vovka", -5.0),
    ]



