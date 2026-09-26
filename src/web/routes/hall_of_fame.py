"""Hall of Fame and Tournament Circuits Blueprint for TTA-Glicko2-WHR.

Provides comprehensive coverage of official TTA tournaments:
- Rulebooks, Regulations & Mathematical Structure Synopses
- Historical Season Counts & Self-Derived Match Participation Metrics
- Dedicated Trophyboards & Halls of Fame (dynamically derived from match archives)
- Fact-based Success Stories & Highlights for Master+ (M+) Profiles
- All-Time Highest Scoring Division Records with complete Opponent details
"""
from typing import Optional, Dict, Any, List
from flask import Blueprint, render_template, abort, redirect, url_for, request
from src.data.db import get_connection
from src.data.hall_of_fame import (
    derive_hall_of_fame_data,
    get_premier_single_game_records_with_opponents,
    get_premier_seasonal_records
)

hall_of_fame_bp = Blueprint('hall_of_fame', __name__, url_prefix='/hall_of_fame')

TOURNAMENT_SERIES = {
    "international": {
        "slug": "international",
        "name": "International Championship",
        "short_name": "International (3/4P)",
        "subtitle": "3/4-Player Competitive Format",
        "player_count": "3/4",
        "format_badge": "3/4-Player League",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 31673,
        "seasons_count": 34,
        "active_range": "2016 – Present (Current: Season 34)",
        "icon": "🌐",
        "summary": "The premier 3/4-player competitive league in Through the Ages. Structured across hierarchical skill divisions (Diamond/Grandmaster, Platinum, Gold, Silver, Bronze, Wood) with quarterly promotion and relegation.",
        "rules": [
            "7 players per division playing a standard seasonal schedule of 7 matches (4 four-player games and 3 three-player games).",
            "Scoring System: 4-Player games award 6/3/1/0 points; 3-Player games award 5/2/0 points (ties split points equally).",
            "Theoretical Seasonal Maximum: (4 x 6) + (3 x 5) = 39.0 points.",
            "Divisional pyramid: Grandmaster, Master (1 & 2), Platinum (1-4), Gold (1-8), Silver (1-14), Bronze (1-14), Wood (1-10).",
            "Top division crowns the official International Champion each season."
        ],
        "stories": [
            {
                "player": "Weidenbaum",
                "badge": "Dynastic Record",
                "title": "The Golden Hexa-Crown • 6 International Titles & 9 Podiums",
                "text": "Grandmaster Weidenbaum holds the all-time championship record in the International Championship with 6 GM Division titles, 2 runner-up finishes, and 1 bronze across 14 competitive seasons (accumulating 282 Hall of Fame points)."
            },
            {
                "player": "Genghisip",
                "badge": "Podium Benchmark",
                "title": "All-Time Medal Leader • 11 Top-3 Finishes & 4 Titles",
                "text": "Holding the all-time record for total podium finishes in the International Championship, Genghisip captured 4 Gold medals, 2 Silvers, and 5 Bronzes across 15 recorded seasons, compiling an all-time high 299 Hall of Fame points."
            },
            {
                "player": "DANeo",
                "badge": "Record Campaign",
                "title": "All-Time Scoring Season • 36.0 / 39.0 Points & Premier Title",
                "text": "DANeo authored one of the most dominant seasonal campaigns in premier 4-player history during Season 31, scoring 36.0 out of a maximum 39.0 points in the Grandmaster Division to claim the Gold crown."
            }
        ]
    },
    "intermezzo": {
        "slug": "intermezzo",
        "name": "Intermezzo Championship",
        "short_name": "Intermezzo (3P)",
        "subtitle": "3-Player Competitive Format",
        "player_count": 3,
        "format_badge": "3-Player League",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 24872,
        "seasons_count": 30,
        "active_range": "2018 – Present (Current: Season 30)",
        "icon": "⚔️",
        "summary": "The premier 3-player competitive league. Characterized by high tactical tension, rapid turn pacing, and razor-thin military balance.",
        "rules": [
            "5 players per division in a round-robin schedule totaling 10 matches per division.",
            "Each player competes in exactly 6 games per season (3-player tables paired with every pair of division rivals).",
            "Scoring System: 1st Place = 5 pts, 2nd Place = 2 pts, 3rd Place = 0 pts (ties split points equally).",
            "Theoretical Seasonal Maximum: 6 games x 5.0 pts = 30.0 points.",
            "Multi-divisional ladder structure with Master 1 / Diamond as the highest tier."
        ],
        "stories": [
            {
                "player": "Weidenbaum",
                "badge": "All-Time Dynasty",
                "title": "Eight-Time Champion • 15 Premier Podiums",
                "text": "Weidenbaum stands as the most decorated champion in Intermezzo history, claiming 8 Gold medals, 3 Silver medals, and 4 Bronze medals across 17 seasons, totaling an unmatched 314 Hall of Fame points."
            },
            {
                "player": "Martin_Pecheur",
                "badge": "Triple Champion",
                "title": "World Champion Pedigree • 3 Titles & 8 Podiums",
                "text": "Martin_Pecheur captured 3 Intermezzo Championships, 3 runner-up finishes, and 2 bronze medals across 10 seasons (172 Hall of Fame points)."
            }
        ]
    },
    "royal_league": {
        "slug": "royal_league",
        "name": "Royal League",
        "short_name": "Royal League (2P)",
        "subtitle": "2-Player Competitive Format",
        "player_count": 2,
        "format_badge": "2-Player Duel",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 14740,
        "seasons_count": 9,
        "active_range": "2024 – Present (Current: Season 9)",
        "icon": "👑",
        "summary": "The premier 2-player recurrent championship. Pure head-to-head duels where military mastery and zero-sum tactical calculations are absolute.",
        "rules": [
            "2-player head-to-head matches exclusively under medium async with 48h reserve per Age.",
            "8 players per division playing 7 weekly match rounds against all group opponents (28 matches total; max 14.0 pts).",
            "Points: 2 for win, 1 for draw, 0 for loss.",
            "Tiebreaker Protocol: 1st tiebreaker is Head-to-Head (H2H) match results between tied players. If unresolved for critical promotion, relegation, or podium finishes, official staged playoff tiebreaker tournaments are run.",
            "Fibonacci-pyramidal divisional hierarchy: Emperor (Premier), King, Prince, Duke, Marquess, Count, Viscount, Baron."
        ],
        "stories": [
            {
                "player": "DANeo",
                "badge": "Reigning Emperor Champion",
                "title": "Season 9 Emperor Gold & Multi-Podium Legend",
                "text": "DANeo captured the Season 9 Royal League Emperor Division Championship with a 6W-1L (12.0 pts) performance, alongside two Silver Medals in Season 4 and Season 7."
            },
            {
                "player": "saru",
                "badge": "Two-Time Emperor Champion",
                "title": "Back-to-Back Titles & Season 9 Silver",
                "text": "saru captured back-to-back Royal League Premier Emperor Division titles in Season 7 and Season 8, followed by a Silver finish in Season 9 (clinching on H2H tiebreaker)."
            },
            {
                "player": "vanishadow",
                "badge": "Inaugural Dynasty",
                "title": "Inaugural Back-to-Back Champion (Season 1 & 2)",
                "text": "vanishadow claimed the first two Royal League championships in history, capturing Gold in Season 1 and Season 2, followed by a Silver finish in Season 3."
            }
        ]
    },
    "worlds": {
        "slug": "worlds",
        "name": "Through the Ages World Championship",
        "short_name": "World Championship",
        "subtitle": "4-Player Competitive Format",
        "player_count": 4,
        "format_badge": "Annual World Championship",
        "frequency": "Annual (Every Year)",
        "total_matches": 31121,
        "seasons_count": 4,
        "active_range": "2023 – Present (Next: 2027)",
        "icon": "🏆",
        "summary": "The pinnacle of competitive Through the Ages. An annual championship bringing together the top qualified competitors worldwide across multi-stage preliminary groups, playoff brackets, and championship finals. (Note: historical format regulations have evolved across editions, and future editions may introduce new architectures).",
        "rules": [
            "Annual world championship staged across multi-round qualifying and playoff brackets.",
            "Historically features progressive group stages (Stage 1 & 2) and upper/lower elimination playoff brackets (Stage 3 & 4).",
            "Format regulations evolve over time with special structures planned for upcoming editions.",
            "Winner receives the permanent World Champion title badge and exclusive Crown WC distinction."
        ],
        "stories": [
            {
                "player": "a440",
                "badge": "Reigning World Champion",
                "title": "The 2025 World Championship Title",
                "text": "a440 captured the 2025 Through the Ages World Championship, surviving the grueling multi-stage qualification and navigating the Stage 4 Upper playoff bracket to claim the world crown."
            },
            {
                "player": "Martin_Pecheur",
                "badge": "2024 World Champion",
                "title": "Playoff Sweep & World Championship Crown",
                "text": "Martin_Pecheur swept the 2024 World Championship playoff brackets, defeating top grandmasters in the championship finals."
            },
            {
                "player": "Weidenbaum",
                "badge": "Inaugural World Champion",
                "title": "The Inaugural 2023 World Championship",
                "text": "Weidenbaum was crowned the inaugural Through the Ages World Champion in 2023, adding the definitive global title to his record 6 International and 8 Intermezzo league championships."
            }
        ]
    },
    "grand_slams": {
        "slug": "grand_slams",
        "name": "Grand Slams & Championship Cups",
        "short_name": "Grand Slams",
        "subtitle": "4-Player Major Open Format",
        "player_count": 4,
        "format_badge": "Major Cups & Slams",
        "frequency": "Annual / Seasonal Majors",
        "total_matches": 12868,
        "seasons_count": 6,
        "active_range": "2023 – Present",
        "icon": "🎾",
        "summary": "Prestigious open championships and multi-stage endurance cups: Survivors Cup (3P survival elimination), Wimbledon TTA (1v1 knockout duel bracket), French Open (3P/4P clay season major), Eiffel Tower Tournament (floor climbing stages to The Top), and Slow Burn.",
        "rules": [
            "Survivors Cup: 11 progressive stages of 3-player survival tables with cuts to Upper/Lower semifinals and Grand Finals.",
            "Wimbledon TTA: Direct 2-player knockout duel rounds through to Quarterfinals, Semifinals, and Finals.",
            "Eiffel Tower: Multi-level qualification climbing up the tower to 'The Top' elite division.",
            "Slow Burn: Extended multi-month endurance rounds culminating in a 3-game Finals series."
        ],
        "stories": [
            {
                "player": "Grozz",
                "badge": "Survivors Cup Champion",
                "title": "2026 Survivors Cup Winner",
                "text": "Grozz conquered the 11-stage 2026 Survivors Cup, triumphing in the Grand Final (213.0 pts) against Weidenbaum (208.0 pts) and Sellux (201.0 pts)."
            },
            {
                "player": "wolvs",
                "badge": "Slow Burn Champion",
                "title": "Season 15 Slow Burn Sweep",
                "text": "wolvs swept all 3 games in the Season 15 Slow Burn Finals (218, 281, 168 pts) to claim the championship over saru and DiddleySquat."
            }
        ]
    },
    "ladders": {
        "slug": "ladders",
        "name": "Competitive Ladders (Mercurial, Sodium & Transcontinental)",
        "short_name": "Competitive Ladders",
        "subtitle": "2 & 3-Player Continuous Ladder Format",
        "player_count": "2/3",
        "format_badge": "Tiered Ladders",
        "frequency": "Continuous / Quarterly",
        "total_matches": 7980,
        "seasons_count": 16,
        "active_range": "2017 – Present",
        "icon": "🪜",
        "summary": "Perpetual rung-based ladders where competitors battle in 3-player and 2-player encounters to ascend through dynamic tier rankings.",
        "rules": [
            "Mercurial Ladder: Rolling periodic element tiers (Hydrogen, Helium ... Neon, Sodium) with performance rung promotions.",
            "Sodium Ladder: Continuous tiered metal ladders across ascending rungs.",
            "Transcontinental Ladder (TCL): 100-stage continuous challenge ladder."
        ],
        "stories": [
            {
                "player": "wolvs",
                "badge": "Ladder Legend",
                "title": "All-Time Ladder Match Leader",
                "text": "wolvs has compiled the highest match volume and victory counts across the competitive ladder circuits."
            }
        ]
    }
}


def get_populated_tournament_series(hof_data: Optional[dict] = None) -> dict:
    """Returns TOURNAMENT_SERIES dynamically populated with real-time match totals and season figures."""
    if hof_data is None:
        hof_data = derive_hall_of_fame_data()
    series_metrics = hof_data.get('series_metrics', {})

    populated = {}
    for slug, base in TOURNAMENT_SERIES.items():
        s = dict(base)
        if slug in series_metrics:
            s['total_matches'] = series_metrics[slug].get('total_matches', s['total_matches'])
            s['seasons_count'] = series_metrics[slug].get('seasons_count', s['seasons_count'])
            s['active_range'] = series_metrics[slug].get('active_range', s['active_range'])
        populated[slug] = s
    return populated


@hall_of_fame_bp.route('')
def index():
    """Hall of Fame overview hub page."""
    force = request.args.get('refresh') == '1'
    hof_data = derive_hall_of_fame_data(force_refresh=force)
    series_map = get_populated_tournament_series(hof_data=hof_data)
    return render_template(
        'tournaments/hub.html',
        series_list=list(series_map.values()),
        hof_data=hof_data
    )


@hall_of_fame_bp.route('/<series_slug>')
def series_detail(series_slug):
    """Detailed showcase page for a specific tournament series in Hall of Fame."""
    force = request.args.get('refresh') == '1'
    hof_data = derive_hall_of_fame_data(force_refresh=force)
    series_map = get_populated_tournament_series(hof_data=hof_data)
    series = series_map.get(series_slug.lower())
    if not series:
        abort(404)

    # Inject dynamically derived trophyboard
    if series_slug == 'royal_league':
        series['trophyboard'] = hof_data['rl_board']
    elif series_slug == 'intermezzo':
        series['trophyboard'] = hof_data['im_board']
    elif series_slug == 'international':
        series['trophyboard'] = hof_data['ic_board']
    elif series_slug == 'worlds':
        series['trophyboard'] = hof_data['wc_board']
    elif series_slug == 'grand_slams':
        series['trophyboard'] = hof_data['gs_board']
    elif series_slug == 'ladders':
        series['trophyboard'] = hof_data['ladder_board']

    records = get_premier_single_game_records_with_opponents(series_slug.lower(), limit=10)
    seasonal_records = get_premier_seasonal_records(series_slug.lower(), limit=10)
    return render_template(
        'tournaments/detail.html',
        series=series,
        all_series=list(series_map.values()),
        records=records,
        seasonal_records=seasonal_records,
        hof_data=hof_data
    )

