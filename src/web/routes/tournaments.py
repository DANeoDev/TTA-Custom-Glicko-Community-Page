"""Tournaments Hub and Dedicated Series Pages for TTA-Glicko2-WHR.

Provides comprehensive coverage of official TTA tournaments:
- Rulebooks & Format Synopses
- Historical Season Counts & Participation Metrics
- Dedicated Trophyboards & Halls of Fame (from official records)
- Fact-based Success Stories & Highlights for Master+ (M+) Profiles
- All-Time Highest Scoring Division Records from database match history
"""
from flask import Blueprint, render_template, abort
import re
from collections import defaultdict
from src.data.db import get_connection

tournaments_bp = Blueprint('tournaments', __name__, url_prefix='/tournaments')

TOURNAMENT_SERIES = {
    "international": {
        "slug": "international",
        "name": "International Championship",
        "short_name": "International (4P)",
        "player_count": 4,
        "format_badge": "4-Player League",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 30638,
        "seasons_count": 33,
        "active_range": "2016 – Present (Current: Season 33)",
        "icon": "🌐",
        "summary": "The premier 4-player competitive league in Through the Ages. Structured across hierarchical skill divisions (Diamond/Master, Platinum, Gold, Silver, Bronze) with quarterly promotion and relegation.",
        "rules": [
            "4 players per match with standard competitive digital turn timer.",
            "Divisional pyramid: Master 1 / Diamond (Premier), Platinum, Gold, Silver, and Bronze divisions.",
            "Seasonal points awarded based on final match placement (1st through 4th).",
            "Top performers earn automatic promotion; bottom finishers are relegated to the next tier.",
            "All completed matches are fully integrated into official 4-Player Glicko-2 and WHR ratings."
        ],
        "trophyboard": [{'player': 'Weidenbaum', 'gold': 6, 'silver': 2, 'bronze': 1, 'total': 9, 'points': 282.0, 'title': 'WC'}, {'player': 'Genghisip', 'gold': 4, 'silver': 2, 'bronze': 5, 'total': 11, 'points': 299.0, 'title': 'GM'}, {'player': 'LeonC', 'gold': 4, 'silver': 0, 'bronze': 1, 'total': 5, 'points': 143.0, 'title': 'GM'}, {'player': 'frotes', 'gold': 3, 'silver': 1, 'bronze': 0, 'total': 4, 'points': 132.0, 'title': 'GM'}, {'player': 'silent_x111', 'gold': 2, 'silver': 1, 'bronze': 4, 'total': 7, 'points': 195.0, 'title': 'GM'}, {'player': 'whsvin', 'gold': 2, 'silver': 1, 'bronze': 0, 'total': 3, 'points': 130.0, 'title': 'GM'}, {'player': 'Grozz', 'gold': 2, 'silver': 1, 'bronze': 0, 'total': 3, 'points': 74.0, 'title': 'GM'}, {'player': 'Airren', 'gold': 1, 'silver': 4, 'bronze': 0, 'total': 5, 'points': 126.0, 'title': 'GM'}, {'player': 'Wawrzyniec', 'gold': 1, 'silver': 3, 'bronze': 0, 'total': 4, 'points': 129.0, 'title': 'GM'}, {'player': 'Pascalotopia', 'gold': 1, 'silver': 1, 'bronze': 0, 'total': 2, 'points': 97.0, 'title': 'GM'}, {'player': 'Majondor', 'gold': 1, 'silver': 1, 'bronze': 0, 'total': 2, 'points': 85.0, 'title': 'GM'}, {'player': 'pajada', 'gold': 1, 'silver': 0, 'bronze': 3, 'total': 4, 'points': 178.5, 'title': 'GM'}, {'player': 'pv4', 'gold': 1, 'silver': 0, 'bronze': 1, 'total': 2, 'points': 115.0, 'title': 'GM'}, {'player': 'Toper', 'gold': 1, 'silver': 0, 'bronze': 1, 'total': 2, 'points': 45.0, 'title': 'GM'}, {'player': 'DANeo', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 48.0, 'title': 'GM'}, {'player': 'a440', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 33.0, 'title': 'WC'}, {'player': 'AaronGreen', 'gold': 0, 'silver': 4, 'bronze': 0, 'total': 4, 'points': 129.0, 'title': 'GM'}, {'player': 'funestus', 'gold': 0, 'silver': 3, 'bronze': 0, 'total': 3, 'points': 130.0, 'title': 'GM'}, {'player': 'Eepogi', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 85.0, 'title': 'M'}, {'player': 'Lambda', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 78.0, 'title': 'M'}, {'player': 'mwi', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 68.0, 'title': 'M'}, {'player': 'invalidName', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 49.0, 'title': 'M'}, {'player': 'Tamirys', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 78.0, 'title': 'M'}, {'player': 'DrRerNate', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 70.0, 'title': 'M'}, {'player': 'Binki', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 55.0, 'title': 'M'}, {'player': 'TryAndStopUs', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 26.5, 'title': 'M'}, {'player': 'Martin_Pecheur', 'gold': 0, 'silver': 0, 'bronze': 2, 'total': 2, 'points': 106.0, 'title': 'WC'}, {'player': 'Dirkules', 'gold': 0, 'silver': 0, 'bronze': 2, 'total': 2, 'points': 50.0, 'title': 'M'}, {'player': 'Fizi', 'gold': 0, 'silver': 0, 'bronze': 2, 'total': 2, 'points': 46.0, 'title': 'M'}, {'player': 'Footloop', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 55.0, 'title': 'M'}, {'player': 'Sandwhale', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 35.0, 'title': 'M'}, {'player': 'dannyboy14', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 32.0, 'title': 'M'}, {'player': 'totsilence', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 31.0, 'title': 'M'}, {'player': 'hihihiji', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 28.0, 'title': 'M'}, {'player': 'qhung49', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 23.0, 'title': 'M'}, {'player': 'DJParson', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 49.5, 'title': 'M'}, {'player': 'ChipsAhoya', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 48.0, 'title': 'M'}, {'player': 'Palino', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 46.0, 'title': 'M'}, {'player': 'Cyphen', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 42.0, 'title': 'M'}, {'player': 'PhiTrigger', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 35.0, 'title': 'M'}, {'player': 'Arne', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 31.0, 'title': 'M'}, {'player': 'Covfefe', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 29.0, 'title': 'M'}, {'player': 'Tordread', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 29.0, 'title': 'M'}, {'player': 'takusto_ii', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 26.0, 'title': 'M'}, {'player': 'slig123', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 24.5, 'title': 'M'}, {'player': 'wolvs', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 22.0, 'title': 'M'}, {'player': 'JCleek', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 22.0, 'title': 'M'}, {'player': 'Octavian', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 22.0, 'title': 'M'}, {'player': 'saru', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 19.0, 'title': 'M'}, {'player': 'JeremyBrokaw', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 14.0, 'title': 'M'}, {'player': 'Hierostrafio', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 12.0, 'title': 'M'}, {'player': 'Lemmingsplayer', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 11.0, 'title': 'M'}, {'player': 'Grogmir', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.0, 'title': 'M'}, {'player': 'BlixLT', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.0, 'title': 'M'}, {'player': 'Vovka', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 8.0, 'title': 'M'}, {'player': 'mushan', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 6.0, 'title': 'M'}, {'player': 'Himmelstosh', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 4.0, 'title': 'M'}, {'player': 'Veivi', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 4.0, 'title': 'M'}],
        "stories": [
            {
                "player": "Weidenbaum",
                "badge": "Dynastic Record",
                "title": "The Golden Hexa-Crown • 6 International Titles & 9 Podiums",
                "text": "Grandmaster Weidenbaum holds the all-time championship record in the International Championship with 6 Diamond Division titles, 2 runner-up finishes, and 1 bronze across 14 competitive seasons (accumulating 282 Hall of Fame points). His multi-season longevity and consistency in 4-player competition established the benchmark against which all top-tier international competitors are measured."
            },
            {
                "player": "Genghisip",
                "badge": "Podium Benchmark",
                "title": "All-Time Medal Leader • 11 Top-3 Finishes & 4 Titles",
                "text": "Holding the all-time record for total podium finishes in the International Championship, Genghisip captured 4 Gold medals, 2 Silvers, and 5 Bronzes across 15 recorded seasons, compiling an all-time high 299 Hall of Fame points. Genghisip's career is marked by unprecedented podium endurance at the highest division of 4-player competitive play."
            },
            {
                "player": "LeonC",
                "badge": "Title Specialist",
                "title": "Four-Time Champion • 5 Podiums in 5 Seasons",
                "text": "LeonC achieved one of the most remarkable title-conversion rates in league history, converting 5 premier seasons into 4 Gold medals and 1 Bronze (143 Hall of Fame points), cementing his reputation as an elite 4-player champion."
            },
            {
                "player": "DANeo",
                "badge": "Record Campaign",
                "title": "All-Time Scoring Season • 39.0 / 42.0 Points & Premier Title",
                "text": "DANeo authored the most dominant seasonal campaign in premier 4-player history during Season 31, scoring 39.0 out of a maximum 42.0 points (6 Wins, 1 Second Place across 7 matches in the Grandmaster Division) to claim the International Championship Gold crown against the highest-ranked field in Through the Ages."
            }
        ]
    },
    "intermezzo": {
        "slug": "intermezzo",
        "name": "Intermezzo Championship",
        "short_name": "Intermezzo (3P)",
        "player_count": 3,
        "format_badge": "3-Player League",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 24872,
        "seasons_count": 30,
        "active_range": "2018 – Present (Current: Season 30)",
        "icon": "⚔️",
        "summary": "The premier 3-player competitive league. Characterized by high tactical tension, rapid turn pacing, and razor-thin military balance.",
        "rules": [
            "3 players per match with fast async timing.",
            "Multi-divisional ladder structure with Master 1 / Grandmaster 1 as the highest tier.",
            "Match weighting calibrated for 3-player dynamics (w = 0.50 in MP-weighted Glicko-2).",
            "Top division crowns the official Intermezzo Champion each season."
        ],
        "trophyboard": [{'player': 'Weidenbaum', 'gold': 8, 'silver': 3, 'bronze': 4, 'total': 15, 'points': 314.0, 'title': 'WC'}, {'player': 'Martin_Pecheur', 'gold': 3, 'silver': 3, 'bronze': 2, 'total': 8, 'points': 172.0, 'title': 'WC'}, {'player': 'silent_x111', 'gold': 3, 'silver': 1, 'bronze': 1, 'total': 5, 'points': 112.0, 'title': 'GM'}, {'player': 'pv4', 'gold': 3, 'silver': 0, 'bronze': 1, 'total': 4, 'points': 113.5, 'title': 'GM'}, {'player': 'totsilence', 'gold': 2, 'silver': 2, 'bronze': 2, 'total': 6, 'points': 100.0, 'title': 'GM'}, {'player': 'wolvs', 'gold': 2, 'silver': 2, 'bronze': 1, 'total': 5, 'points': 111.0, 'title': 'GM'}, {'player': 'DrRerNate', 'gold': 2, 'silver': 1, 'bronze': 1, 'total': 4, 'points': 79.0, 'title': 'GM'}, {'player': 'AaronGreen', 'gold': 2, 'silver': 0, 'bronze': 0, 'total': 2, 'points': 82.0, 'title': 'GM'}, {'player': 'pajada', 'gold': 1, 'silver': 3, 'bronze': 2, 'total': 6, 'points': 141.5, 'title': 'GM'}, {'player': 'DJParson', 'gold': 1, 'silver': 1, 'bronze': 1, 'total': 3, 'points': 74.0, 'title': 'GM'}, {'player': 'Palino', 'gold': 1, 'silver': 1, 'bronze': 1, 'total': 3, 'points': 54.0, 'title': 'GM'}, {'player': 'Veivi', 'gold': 1, 'silver': 1, 'bronze': 1, 'total': 3, 'points': 44.0, 'title': 'GM'}, {'player': 'DireNTropy', 'gold': 1, 'silver': 1, 'bronze': 0, 'total': 2, 'points': 52.0, 'title': 'GM'}, {'player': 'sqwndw', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 30.0, 'title': 'GM'}, {'player': 'Grozz', 'gold': 0, 'silver': 2, 'bronze': 2, 'total': 4, 'points': 69.0, 'title': 'M'}, {'player': 'Eske', 'gold': 0, 'silver': 2, 'bronze': 1, 'total': 3, 'points': 45.5, 'title': 'M'}, {'player': 'Eepogi', 'gold': 0, 'silver': 2, 'bronze': 0, 'total': 2, 'points': 46.0, 'title': 'M'}, {'player': 'Wawrzyniec', 'gold': 0, 'silver': 2, 'bronze': 0, 'total': 2, 'points': 34.5, 'title': 'M'}, {'player': 'Tamirys', 'gold': 0, 'silver': 1, 'bronze': 2, 'total': 3, 'points': 50.5, 'title': 'M'}, {'player': 'kuchjir', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 42.0, 'title': 'M'}, {'player': 'PhiTrigger', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'points': 39.0, 'title': 'M'}, {'player': 'Dots', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 35.0, 'title': 'M'}, {'player': 'qhung49', 'gold': 0, 'silver': 0, 'bronze': 2, 'total': 2, 'points': 37.0, 'title': 'M'}, {'player': 'Footloop', 'gold': 0, 'silver': 0, 'bronze': 2, 'total': 2, 'points': 34.0, 'title': 'M'}, {'player': 'DANeo', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 28.0, 'title': 'M'}, {'player': 'Hierostrafio', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 18.0, 'title': 'M'}, {'player': 'Gandin', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 21.0, 'title': 'M'}, {'player': 'BlixLT', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 13.0, 'title': 'M'}, {'player': 'LaoHuang', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 12.0, 'title': 'M'}, {'player': 'mlhibou', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 12.0, 'title': 'M'}, {'player': 'takusto_II', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 11.0, 'title': 'M'}, {'player': 'ranch99', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 10.0, 'title': 'M'}, {'player': 'Angor', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 10.0, 'title': 'M'}, {'player': 'barboucha', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 10.0, 'title': 'M'}, {'player': 'frotes', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.5, 'title': 'M'}, {'player': 'dannyboy14', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.0, 'title': 'M'}, {'player': 'deluks917', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.0, 'title': 'M'}, {'player': 'Kimmo', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 9.0, 'title': 'M'}, {'player': 'Lech', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 8.0, 'title': 'M'}, {'player': 'Majondor', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 8.0, 'title': 'M'}, {'player': 'Oprah', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 8.0, 'title': 'M'}, {'player': 'ERock37', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 8.0, 'title': 'M'}, {'player': 'scipio238', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 7.0, 'title': 'M'}, {'player': 'Vantablack', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 7.0, 'title': 'M'}, {'player': 'wartin', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 6.0, 'title': 'M'}, {'player': 'DiddleySquat', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 6.0, 'title': 'M'}, {'player': 'ChipsAhoya', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 5.0, 'title': 'M'}, {'player': 'Praetorianer', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 5.0, 'title': 'M'}, {'player': 'Andrethegiant', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 4.0, 'title': 'M'}, {'player': 'iyakhoop', 'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0, 'points': 4.0, 'title': 'M'}],
        "stories": [
            {
                "player": "Weidenbaum",
                "badge": "All-Time Dynasty",
                "title": "Eight-Time Champion • 15 Premier Podiums",
                "text": "Weidenbaum stands as the most decorated champion in Intermezzo history, claiming 8 Gold medals, 3 Silver medals, and 4 Bronze medals across 17 seasons, totaling an unmatched 314 Hall of Fame points. No other player in 3-player digital Through the Ages competition has reached double-digit medals in the premier division."
            },
            {
                "player": "Martin_Pecheur",
                "badge": "Triple Champion",
                "title": "World Champion Pedigree • 3 Titles & 8 Podiums",
                "text": "Martin_Pecheur captured 3 Intermezzo Championships, 3 runner-up finishes, and 2 bronze medals across 10 seasons (172 Hall of Fame points). Combined with his 2024 World Championship and multiple Royal League crowns, his 8 Intermezzo podiums solidify his standing across all competitive formats."
            },
            {
                "player": "silent_x111",
                "badge": "Triple Champion",
                "title": "Triple Intermezzo Champion • 5 Premier Podiums",
                "text": "silent_x111 earned 3 Gold medals, 1 Silver, and 1 Bronze in top-division Intermezzo play (112 Hall of Fame points), standing alongside pv4 and Martin_Pecheur as one of only four competitors in history to secure at least 3 Intermezzo gold medals."
            },
            {
                "player": "pv4",
                "badge": "Triple Champion",
                "title": "10-Season Top-Tier Consistency • 3 Titles",
                "text": "Grandmaster pv4 clinched 3 Intermezzo titles and 1 Bronze across 10 competitive seasons, amassing 113.5 Hall of Fame points. His persistent presence at the summit of 3-player rankings spans multiple competitive cycles."
            }
        ]
    },
    "royal_league": {
        "slug": "royal_league",
        "name": "Royal League",
        "short_name": "Royal League (2P)",
        "player_count": 2,
        "format_badge": "2-Player Duel",
        "frequency": "Quarterly (4 seasons / year)",
        "total_matches": 13049,
        "seasons_count": 8,
        "active_range": "2024 – Present (Current: Season 8)",
        "icon": "👑",
        "summary": "The premier 2-player recurrent championship. Pure head-to-head duels where military mastery and zero-sum tactical calculations are absolute.",
        "rules": [
            "2-player head-to-head matches exclusively under medium async with 48h reserve per Age.",
            "Each season consists of 7 weekly match rounds against all 7 group opponents.",
            "Fibonacci-pyramidal divisional structure: Emperor (Premier 1 group), King (1 group), Prince (2 groups), Duke (3 groups), Marquess, Count, Viscount, Baron, Knight.",
            "Points: 2 for win, 1 for draw, 0 for loss. Tie-breakers resolved by head-to-head points and official rematches.",
            "Double-promotion for best group winners; relegation for bottom 2 spots in each tier."
        ],
        "trophyboard": [{'player': 'saru', 'gold': 2, 'silver': 1, 'bronze': 1, 'total': 4, 'title': 'GM'}, {'player': 'vanishadow', 'gold': 2, 'silver': 1, 'bronze': 0, 'total': 3, 'title': 'GM'}, {'player': 'Martin_Pecheur', 'gold': 2, 'silver': 0, 'bronze': 4, 'total': 6, 'title': 'WC'}, {'player': 'majondor', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'GM'}, {'player': 'ben0728', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'GM'}, {'player': 'DANeo', 'gold': 0, 'silver': 2, 'bronze': 0, 'total': 2, 'title': 'GM'}, {'player': 'Grozz', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'title': 'GM'}, {'player': 'Weidenbaum', 'gold': 0, 'silver': 1, 'bronze': 1, 'total': 2, 'title': 'WC'}, {'player': 'Airren', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'title': 'GM'}, {'player': 'SandHippo', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'title': 'M'}, {'player': 'yaop', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'title': 'M'}, {'player': 'pv4', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'title': 'GM'}],
        "stories": [
            {
                "player": "saru",
                "badge": "Reigning Champion",
                "title": "Back-to-Back Titles (2026 Q1 & Q2) • 4 Total Podiums",
                "text": "saru captured back-to-back Royal League Premier Emperor Division titles in 2026 Q1 and 2026 Q2, alongside Silver in 2025 Q4 and Bronze in 2025 Q2. With 4 podiums in 8 quarters, saru is the leading duel finalist in modern Royal League competition."
            },
            {
                "player": "vanishadow",
                "badge": "Inaugural Dynasty",
                "title": "Inaugural Back-to-Back Champion (2024 Q3 & Q4)",
                "text": "vanishadow claimed the first two Royal League championships in history, capturing Gold in 2024 Q3 and 2024 Q4, followed by a Silver finish in 2025 Q1. Holding a pristine 2 Gold, 1 Silver record across his first three seasons in the Emperor Division, vanishadow set the historical standard for competitive head-to-head duel play."
            },
            {
                "player": "Martin_Pecheur",
                "badge": "Dual Titleholder",
                "title": "Two-Time Champion • Record 6 Total Podiums",
                "text": "World Champion Martin_Pecheur conquered the Royal League with Gold in 2025 Q2 and 2025 Q4, alongside 4 Bronze finishes (2024 Q3, 2025 Q1, 2025 Q3, 2026 Q2). His 6 total podiums represent the highest medal tally in Royal League history."
            },
            {
                "player": "DANeo",
                "badge": "Dual Finalist",
                "title": "Two-Time Emperor Silver Medalist (2025 Q2 & 2026 Q1)",
                "text": "DANeo achieved two Premier Emperor Division Silver Medals in Royal League (2025 Q2 and 2026 Q1), contending in the grand finals against world-class duel competition and logging multiple 300+ point matches in Emperor division play."
            }
        ]
    },
    "worlds": {
        "slug": "worlds",
        "name": "Through the Ages World Championship",
        "short_name": "World Championship",
        "player_count": 4,
        "format_badge": "Biennial Championship",
        "frequency": "Biennial (Every 2 Years)",
        "total_matches": 30674,
        "seasons_count": 3,
        "active_range": "2023 – Present (Next: 2027)",
        "icon": "🏆",
        "summary": "The pinnacle of competitive Through the Ages. A grueling multi-stage championship spanning four qualifying stages and upper/lower playoff brackets.",
        "rules": [
            "Biennial championship bringing together the top qualified competitors worldwide.",
            "Stage 1 & 2: Global group qualification rounds across 3P and 4P formats.",
            "Stage 3 & 4: Elite double-elimination and upper/lower playoff brackets.",
            "Winner receives the permanent World Champion title badge and 2,500 Community Leaderboard points."
        ],
        "trophyboard": [{'player': 'a440', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'WC', 'edition': '2025 (Reigning Champion)'}, {'player': 'Martin_Pecheur', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'WC', 'edition': '2024'}, {'player': 'Weidenbaum', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'WC', 'edition': '2023 (Inaugural)'}],
        "stories": [
            {
                "player": "a440",
                "badge": "Reigning World Champion",
                "title": "The 2025 World Championship Title",
                "text": "a440 captured the 2025 Through the Ages World Championship, surviving the grueling multi-stage qualification and navigating the Stage 4 Upper playoff bracket against the world's highest-rated players to claim the world title."
            },
            {
                "player": "Martin_Pecheur",
                "badge": "2024 World Champion",
                "title": "Playoff Sweep & World Championship Crown",
                "text": "Martin_Pecheur swept the 2024 World Championship playoff brackets, defeating top grandmasters in the championship finals and cementing his place among the all-time greats of competitive board gaming."
            },
            {
                "player": "Weidenbaum",
                "badge": "Inaugural World Champion",
                "title": "The Inaugural 2023 World Championship",
                "text": "Weidenbaum was crowned the inaugural Through the Ages World Champion in 2023, adding the definitive global championship title to his record 6 International and 8 Intermezzo league championships."
            }
        ]
    },
    "grand_slams": {
        "slug": "grand_slams",
        "name": "Grand Slams: Wimbledon & Australian Open",
        "short_name": "Grand Slams",
        "player_count": 4,
        "format_badge": "Major Opens",
        "frequency": "Annual Majors",
        "total_matches": 984,
        "seasons_count": 2,
        "active_range": "2025 – Present",
        "icon": "🎾",
        "summary": "Prestigious open championships featuring large competitor fields, Swiss qualification, and direct elimination finals. Worth up to 1,000 Community Leaderboard points.",
        "rules": [
            "Open registration for all competitive players worldwide.",
            "Swiss rounds followed by knockout playoff brackets.",
            "Full 1,000 points awarded toward the official Community Leaderboard."
        ],
        "trophyboard": [{'player': 'Genghisip', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'title': 'GM'}, {'player': 'Airren', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'title': 'GM'}, {'player': 'Grozz', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'title': 'GM'}],
        "stories": [
            {
                "player": "Genghisip",
                "badge": "Grand Slam Champion",
                "title": "Aussie Open Champion & Open-Bracket Dominance",
                "text": "Grand Slam open tournaments feature massive Swiss qualification fields followed by elimination playoffs. Genghisip captured the Aussie Open title and has consistently navigated high-variance open brackets to reach the final stages of major open events."
            },
            {
                "player": "Airren",
                "badge": "Grand Slam Finalist",
                "title": "Wimbledon Runner-up & Deep Open Bracket Runs",
                "text": "Airren secured the Wimbledon Silver Medal, showcasing exceptional stamina through multi-round open qualification stages and elimination finals."
            }
        ]
    },
    "ladders": {
        "slug": "ladders",
        "name": "Competitive Ladders (Sodium, Mercurial & Transcontinental)",
        "short_name": "Competitive Ladders",
        "player_count": 3,
        "format_badge": "Tiered Ladders",
        "frequency": "Continuous / Annual",
        "total_matches": 5537,
        "seasons_count": 12,
        "active_range": "2020 – Present",
        "icon": "🪜",
        "summary": "Perpetual rung-based ladders where competitors battle in 3-player and 2-player encounters to ascend through dynamic tier rankings.",
        "rules": [
            "Sodium Ladder: Annual ladder across ascending metal tiers with Tier 1 crowning the annual champion.",
            "Mercurial Ladder: 1 game per season with dynamic tier assignment based on rolling performance points.",
            "Transcontinental Ladder: 66 players competing across 22 rungs with 1st place promotion and 3rd place relegation."
        ],
        "trophyboard": [{'player': 'wolvs', 'gold': 10, 'silver': 2, 'bronze': 1, 'total': 13, 'title': 'M'}, {'player': 'pajada', 'gold': 8, 'silver': 3, 'bronze': 2, 'total': 13, 'title': 'M'}, {'player': 'Wawrzyniec', 'gold': 5, 'silver': 2, 'bronze': 0, 'total': 7, 'title': 'M'}, {'player': 'Grozz', 'gold': 5, 'silver': 6, 'bronze': 0, 'total': 11, 'title': 'GM'}, {'player': 'Martin_Pecheur', 'gold': 3, 'silver': 3, 'bronze': 0, 'total': 6, 'title': 'WC'}, {'player': 'Arne', 'gold': 3, 'silver': 2, 'bronze': 0, 'total': 5, 'title': 'M'}, {'player': 'Dazzy', 'gold': 3, 'silver': 1, 'bronze': 0, 'total': 4, 'title': 'M'}, {'player': 'ERock37', 'gold': 3, 'silver': 0, 'bronze': 0, 'total': 3, 'title': 'M'}, {'player': 'Palino', 'gold': 2, 'silver': 0, 'bronze': 0, 'total': 2, 'title': 'M'}, {'player': 'Fourierrr', 'gold': 2, 'silver': 0, 'bronze': 0, 'total': 2, 'title': 'M'}, {'player': 'gomensky', 'gold': 2, 'silver': 0, 'bronze': 0, 'total': 2, 'title': 'M'}, {'player': 'totsilence', 'gold': 1, 'silver': 2, 'bronze': 1, 'total': 4, 'title': 'M'}],
        "stories": [
            {
                "player": "wolvs",
                "badge": "Mercurial Record",
                "title": "10-Time Mercurial Ladder Premium Champion",
                "text": "wolvs holds the all-time record on the Mercurial Ladder with 10 Premium division victories and 13 total top-tier finishes, maintaining an unmatched standard of sustained performance across continuous ladder play."
            },
            {
                "player": "pajada",
                "badge": "Multi-Ladder Master",
                "title": "8 Mercurial Titles & High-Tier Consistency",
                "text": "pajada has captured 8 Mercurial Ladder Premium titles alongside multiple top-tier finishes in the Sodium Ladder, standing as one of the most prolific ladder competitors in competitive history."
            },
            {
                "player": "Wawrzyniec",
                "badge": "Sodium Sovereign",
                "title": "5-Time Sodium Ladder Tier 1 Champion",
                "text": "Wawrzyniec dominates the historical Sodium Ladder records with 5 Tier 1 championships and 2 runner-up finishes, setting the benchmark for performance across ascending ladder tiers."
            }
        ]
    }
}


def get_tournament_records(slug, limit=10):
    """Fetch all-time highest scoring individual games in the highest division."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if slug == 'international':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'International%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'International%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'International%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'International%' AND player4 IS NOT NULL
                )
                WHERE tournament LIKE '%Master 1%' OR tournament LIKE '%Diamond%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'intermezzo':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Intermezzo%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Intermezzo%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Intermezzo%' AND player3 IS NOT NULL
                )
                WHERE tournament LIKE '%Master 1%' OR tournament LIKE '%Grandmaster 1%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'royal_league':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'RL_%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'RL_%'
                )
                WHERE tournament LIKE '%Emperor%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'worlds':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Worlds%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Worlds%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Worlds%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'Worlds%' AND player4 IS NOT NULL
                )
                WHERE tournament LIKE '%Stage 4%' OR tournament LIKE '%Final%' OR tournament LIKE '%Upper%'
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'grand_slams':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Wimbledon%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Wimbledon%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Wimbledon%' AND player3 IS NOT NULL
                    UNION ALL
                    SELECT tournament, date, player4 AS player, score4 AS score FROM matches WHERE tournament LIKE 'Wimbledon%' AND player4 IS NOT NULL
                )
                ORDER BY score DESC LIMIT ?
            """
        elif slug == 'ladders':
            query = """
                SELECT tournament, date, player, score FROM (
                    SELECT tournament, date, player1 AS player, score1 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%'
                    UNION ALL
                    SELECT tournament, date, player2 AS player, score2 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%'
                    UNION ALL
                    SELECT tournament, date, player3 AS player, score3 AS score FROM matches WHERE tournament LIKE 'Sodium%' OR tournament LIKE 'Mercurial%' OR tournament LIKE 'ML_%' AND player3 IS NOT NULL
                )
                ORDER BY score DESC LIMIT ?
            """
        else:
            return []
        cur.execute(query, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_seasonal_points_records(slug, limit=10):
    """Fetch all-time highest scoring season campaigns in the premier division."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute('''
            SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
            FROM matches
        ''').fetchall()

        def assign_points(scores, p_count):
            scores.sort(key=lambda x: x[1], reverse=True)
            if p_count == 4:
                std_pts = [6.0, 3.0, 1.0, 0.0]
            elif p_count == 3:
                std_pts = [5.0, 2.0, 0.0]
            else:
                std_pts = [2.0, 0.0]
            from collections import defaultdict
            groups = defaultdict(list)
            for p, s in scores:
                groups[s].append(p)
            res = []
            idx = 0
            for s in sorted(groups.keys(), reverse=True):
                plist = groups[s]
                k = len(plist)
                pts_chunk = sum(std_pts[idx : idx + k])
                pts_each = pts_chunk / k
                for p in plist:
                    res.append((p, pts_each))
                idx += k
            return res

        campaigns = defaultdict(lambda: {'pts': 0.0, 'games': 0, 'wins': 0, '2nd': 0, 'div': 'Premier', 'date': ''})

        for r in rows:
            t = r['tournament'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0]
            p_count = r['player_count'] if isinstance(r, dict) or hasattr(r, 'keys') else (r[2] or 4)
            p1 = r['player1'] if isinstance(r, dict) or hasattr(r, 'keys') else r[3]
            s1 = r['score1'] if isinstance(r, dict) or hasattr(r, 'keys') else r[4]
            p2 = r['player2'] if isinstance(r, dict) or hasattr(r, 'keys') else r[5]
            s2 = r['score2'] if isinstance(r, dict) or hasattr(r, 'keys') else r[6]
            p3 = r['player3'] if isinstance(r, dict) or hasattr(r, 'keys') else r[7]
            s3 = r['score3'] if isinstance(r, dict) or hasattr(r, 'keys') else r[8]
            p4 = r['player4'] if isinstance(r, dict) or hasattr(r, 'keys') else r[9]
            s4 = r['score4'] if isinstance(r, dict) or hasattr(r, 'keys') else r[10]
            dt = r['date'] if isinstance(r, dict) or hasattr(r, 'keys') else r[1]

            p_scores = []
            if p1 and s1 is not None: p_scores.append((p1, float(s1)))
            if p2 and s2 is not None: p_scores.append((p2, float(s2)))
            if p3 and s3 is not None: p_scores.append((p3, float(s3)))
            if p4 and s4 is not None: p_scores.append((p4, float(s4)))
            if len(p_scores) < 2: continue

            s_num = None
            div = 'Premier'
            is_target = False

            if slug == 'international':
                m = re.search(r'International\s+S(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else ('Master' if s_num >= 28 else 'Premier')
                    if ('Master' in div or 'Grandmaster' in div or 'Diamond' in div or 'Premier' in div):
                        is_target = True
            elif slug == 'intermezzo':
                m = re.search(r'Intermezzo\s+S(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else 'Premier'
                    if ('Master' in div or 'Grandmaster' in div or 'Diamond' in div or 'Premier' in div):
                        is_target = True
            elif slug == 'royal_league':
                m = re.search(r'RL_s(\d+)(?:\s*-\s*([^-]+))?', t, re.IGNORECASE)
                if m:
                    s_num = int(m.group(1))
                    div = m.group(2).strip() if m.group(2) else 'Emperor'
                    if 'Emperor' in div or 'Premier' in div:
                        is_target = True

            if not is_target or s_num is None:
                continue

            season_key = f'Season {s_num}'
            awarded = assign_points(p_scores, p_count)
            for p, pts in awarded:
                c_key = (season_key, p)
                campaigns[c_key]['pts'] += pts
                campaigns[c_key]['games'] += 1
                campaigns[c_key]['div'] = div
                campaigns[c_key]['date'] = dt
                if (p_count == 4 and pts == 6.0) or (p_count == 3 and pts == 5.0) or (p_count == 2 and pts == 2.0):
                    campaigns[c_key]['wins'] += 1
                elif (p_count == 4 and pts == 3.0) or (p_count == 3 and pts == 2.0) or (p_count == 2 and pts == 1.0):
                    campaigns[c_key]['2nd'] += 1

        records = []
        min_games = 5 if slug == 'royal_league' else 6
        for (season_key, p), data in campaigns.items():
            if data['games'] >= min_games:
                records.append({
                    'player': p,
                    'season': season_key,
                    'division': data['div'],
                    'points': data['pts'],
                    'games': data['games'],
                    'wins': data['wins'],
                    'second_places': data['2nd'],
                    'date': data['date']
                })

        records.sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        return records[:limit]
    finally:
        conn.close()


@tournaments_bp.route('')
def index():
    """Tournaments Hub overview page."""
    return render_template('tournaments/hub.html', series_list=list(TOURNAMENT_SERIES.values()))


@tournaments_bp.route('/<series_slug>')
def series_detail(series_slug):
    """Detailed showcase page for a specific tournament series."""
    series = TOURNAMENT_SERIES.get(series_slug.lower())
    if not series:
        abort(404)
    records = get_tournament_records(series_slug.lower(), limit=10)
    seasonal_records = get_seasonal_points_records(series_slug.lower(), limit=10)
    return render_template(
        'tournaments/detail.html',
        series=series,
        all_series=list(TOURNAMENT_SERIES.values()),
        records=records,
        seasonal_records=seasonal_records
    )
