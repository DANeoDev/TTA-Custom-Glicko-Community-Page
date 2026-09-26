"""Hall of Fame and Tournament Statistics Derivation Engine for Through the Ages.

Derives historical standings, podiums, trophyboards, and deep tournament statistics
directly from scraped match records in SQLite:
- Core Major Circuits: World Championship (WCS), International Championship (ICS),
  Intermezzo Championship, and Royal League (with Head-to-Head tiebreaking).
- Grand Slams & Special Championship Cups: Survivors Cup, Wimbledon TTA, French Open,
  Eiffel Tower, Slow Burn.
- Competitive Ladders: Mercurial Ladder, Sodium Ladder, Transcontinental Ladder (TCL).
- Full database synchronization to player_achievements and tournament_records.
"""
import re
import json
import sqlite3
import functools
try:
    import pandas as pd
except ImportError:
    pd = None
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from src.data.db import get_connection


def derive_match_placements(player_scores: List[Tuple[str, float]]) -> List[Tuple[str, int, float]]:
    """Assigns 1-based ranks (handling ties) based on scores descending."""
    valid_scores = [(p, float(s) if s is not None else 0.0) for p, s in player_scores if p]
    if not valid_scores:
        return []
    valid_scores.sort(key=lambda x: x[1], reverse=True)
    
    results = []
    current_rank = 1
    for i, (p, s) in enumerate(valid_scores):
        if i > 0 and s < valid_scores[i-1][1]:
            current_rank = i + 1
        results.append((p, current_rank, s))
    return results


def derive_royal_league_podiums(conn) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """Derives exact Emperor division standings and podiums for all Royal League seasons using H2H tiebreakers."""
    # Official historical seasons (S1 to S8)
    official_seasons = {
        1: {'gold': 'vanishadow', 'silver': 'Weidenbaum', 'bronze': 'Airren'},
        2: {'gold': 'vanishadow', 'silver': 'SandHippo', 'bronze': 'Weidenbaum'},
        3: {'gold': 'ben0728', 'silver': 'vanishadow', 'bronze': 'Martin_Pecheur'},
        4: {'gold': 'Martin_Pecheur', 'silver': 'DANeo', 'bronze': 'saru'},
        5: {'gold': 'majondor', 'silver': 'Grozz', 'bronze': 'Martin_Pecheur'},
        6: {'gold': 'Martin_Pecheur', 'silver': 'saru', 'bronze': 'Grozz'},
        7: {'gold': 'saru', 'silver': 'DANeo', 'bronze': 'pv4'},
        8: {'gold': 'saru', 'silver': 'Martin_Pecheur', 'bronze': 'yaop'},
    }

    # Derive latest Season 9 from matches in database with H2H tiebreak
    rows = conn.execute("""
        SELECT tournament, date, player1, score1, player2, score2
        FROM matches
        WHERE (tournament LIKE 'RL_%' OR tournament LIKE '%Royal League%')
          AND tournament LIKE '%Emperor%'
        ORDER BY date
    """).fetchall()

    season_matches = defaultdict(list)
    for r in rows:
        t = r['tournament']
        m = re.search(r's0?(\d+)', t, re.I) or re.search(r'season\s*0?(\d+)', t, re.I)
        if m:
            s_num = int(m.group(1))
            if s_num >= 9:
                season_matches[s_num].append(r)

    season_podiums = {}
    for s_num, pod in official_seasons.items():
        season_podiums[s_num] = {
            'gold': pod['gold'],
            'silver': pod['silver'],
            'bronze': pod['bronze'],
            'standings': []
        }

    for s_num in sorted(season_matches.keys()):
        m_list = season_matches[s_num]
        players = set()
        pts = defaultdict(float)
        wins = defaultdict(int)
        h2h = defaultdict(lambda: defaultdict(int))
        total_scores = defaultdict(float)

        for r in m_list:
            p1, s1 = r['player1'], r['score1']
            p2, s2 = r['player2'], r['score2']
            if not p1 or not p2:
                continue
            players.add(p1); players.add(p2)
            total_scores[p1] += (s1 if s1 is not None else 0.0)
            total_scores[p2] += (s2 if s2 is not None else 0.0)

            if s1 is not None and s2 is not None:
                if s1 > s2:
                    pts[p1] += 2.0; wins[p1] += 1
                    h2h[p1][p2] += 2
                elif s2 > s1:
                    pts[p2] += 2.0; wins[p2] += 1
                    h2h[p2][p1] += 2
                else:
                    pts[p1] += 1.0; pts[p2] += 1.0
                    h2h[p1][p2] += 1; h2h[p2][p1] += 1

        def compare_rl_players(p_a, p_b):
            if pts[p_a] != pts[p_b]:
                return pts[p_a] - pts[p_b]
            if h2h[p_a][p_b] != h2h[p_b][p_a]:
                return h2h[p_a][p_b] - h2h[p_b][p_a]
            if wins[p_a] != wins[p_b]:
                return wins[p_a] - wins[p_b]
            return total_scores[p_a] - total_scores[p_b]

        sorted_players = sorted(list(players), key=functools.cmp_to_key(compare_rl_players), reverse=True)
        if sorted_players:
            gold = sorted_players[0]
            silver = sorted_players[1] if len(sorted_players) > 1 else None
            bronze = sorted_players[2] if len(sorted_players) > 2 else None

            season_podiums[s_num] = {
                'gold': gold, 'silver': silver, 'bronze': bronze,
                'standings': [(p, pts[p], wins[p]) for p in sorted_players]
            }

    # Aggregate trophyboard
    player_trophies = defaultdict(lambda: {'gold': 0, 'silver': 0, 'bronze': 0, 'points': 0.0})
    for s_num, pod in season_podiums.items():
        if pod['gold']: player_trophies[pod['gold']]['gold'] += 1; player_trophies[pod['gold']]['points'] += 10.0
        if pod['silver']: player_trophies[pod['silver']]['silver'] += 1; player_trophies[pod['silver']]['points'] += 5.0
        if pod['bronze']: player_trophies[pod['bronze']]['bronze'] += 1; player_trophies[pod['bronze']]['points'] += 2.0

    trophyboard = []
    for p, stats in player_trophies.items():
        tot = stats['gold'] + stats['silver'] + stats['bronze']
        if tot > 0:
            trophyboard.append({
                'player': p,
                'gold': stats['gold'],
                'silver': stats['silver'],
                'bronze': stats['bronze'],
                'total': tot,
                'points': stats['points'],
                'title': 'WC' if p in ['a440', 'Martin_Pecheur', 'Weidenbaum'] else ('GM' if stats['gold'] > 0 else 'M')
            })

    trophyboard.sort(key=lambda x: (x['gold'], x['silver'], x['bronze'], x['points']), reverse=True)
    return season_podiums, trophyboard


def derive_intermezzo_podiums(conn) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """Derives Grandmaster (Premier) division standings and podiums for all Intermezzo seasons."""
    season_podiums = {}
    player_trophies = defaultdict(lambda: {'gold': 0, 'silver': 0, 'bronze': 0, 'points': 0.0})

    # 1. Primary: query tournament_records table in SQLite (fully independent of pandas/openpyxl)
    try:
        rows = conn.execute("""
            SELECT player_name, placement, points
            FROM tournament_records
            WHERE tournament_name = 'Intermezzo Championship' AND division LIKE '%Hall of Fame%'
        """).fetchall()
        for r in rows:
            p = r['player_name']
            plc = r['placement'] or ''
            pts_str = r['points'] or ''
            g = int(m.group(1)) if (m := re.search(r'(\d+)x 1st', plc)) else 0
            s = int(m.group(1)) if (m := re.search(r'(\d+)x 2nd', plc)) else 0
            b = int(m.group(1)) if (m := re.search(r'(\d+)x 3rd', plc)) else 0
            pt = float(m.group(1)) if (m := re.search(r'([\d.]+)', pts_str)) else 0.0
            if (g + s + b) > 0 or pt > 0:
                player_trophies[p]['gold'] += g
                player_trophies[p]['silver'] += s
                player_trophies[p]['bronze'] += b
                player_trophies[p]['points'] += pt
    except Exception:
        pass

    # 2. Secondary: fallback to hall_of_fame_fallback.json bundled in repo
    if not player_trophies:
        fb_path = Path(__file__).resolve().parent / "hall_of_fame_fallback.json"
        if fb_path.exists():
            try:
                with open(fb_path, 'r', encoding='utf-8') as f:
                    fb_data = json.load(f).get('intermezzo', [])
                for item in fb_data:
                    p = item['player']
                    player_trophies[p]['gold'] += item.get('gold', 0)
                    player_trophies[p]['silver'] += item.get('silver', 0)
                    player_trophies[p]['bronze'] += item.get('bronze', 0)
                    player_trophies[p]['points'] += item.get('points', 0.0)
            except Exception:
                pass

    # 3. Tertiary: Fallback to Hall of Fame.xlsx if database and JSON were unavailable
    if not player_trophies:
        hof_path = Path("data/tournaments/Hall of Fame.xlsx")
        if pd is not None and hof_path.exists():
            try:
                xl = pd.ExcelFile(hof_path)
                if 'Intermezzo Championship' in xl.sheet_names:
                    df = xl.parse('Intermezzo Championship')
                    for _, row in df.iterrows():
                        p = row.get('Unnamed: 3')
                        if pd.isna(p) or not str(p).strip() or str(p).startswith('Player') or str(p).startswith('Season') or 'ordered by' in str(p) or '*' in str(p):
                            continue
                        p = str(p).strip()
                        gold = int(row['Winner']) if pd.notna(row['Winner']) else 0
                        silver = int(row['Runner-up']) if pd.notna(row['Runner-up']) else 0
                        bronze = int(row['3rd place']) if pd.notna(row['3rd place']) else 0
                        pts = float(row['Points']) if pd.notna(row['Points']) else 0.0
                        if (gold + silver + bronze) > 0 or pts > 0:
                            player_trophies[p]['gold'] += gold
                            player_trophies[p]['silver'] += silver
                            player_trophies[p]['bronze'] += bronze
                            player_trophies[p]['points'] += pts
            except Exception:
                pass

    trophyboard = []
    for p, stats in player_trophies.items():
        tot = stats['gold'] + stats['silver'] + stats['bronze']
        if tot > 0:
            trophyboard.append({
                'player': p,
                'gold': stats['gold'],
                'silver': stats['silver'],
                'bronze': stats['bronze'],
                'total': tot,
                'points': stats['points'],
                'title': 'WC' if p in ['a440', 'Martin_Pecheur', 'Weidenbaum'] else ('GM' if stats['gold'] > 0 else 'M')
            })

    trophyboard.sort(key=lambda x: (x['gold'], x['silver'], x['bronze'], x['points']), reverse=True)
    return season_podiums, trophyboard


def derive_international_podiums(conn) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """Derives Grandmaster / Diamond (Premier) division standings and podiums for all International Championship seasons."""
    season_podiums = {}
    player_trophies = defaultdict(lambda: {'gold': 0, 'silver': 0, 'bronze': 0, 'points': 0.0})

    # 1. Primary: query tournament_records table in SQLite (fully independent of pandas/openpyxl)
    try:
        rows = conn.execute("""
            SELECT player_name, placement, points
            FROM tournament_records
            WHERE tournament_name = 'International Championship' AND division LIKE '%Hall of Fame%'
        """).fetchall()
        for r in rows:
            p = r['player_name']
            plc = r['placement'] or ''
            pts_str = r['points'] or ''
            g = int(m.group(1)) if (m := re.search(r'(\d+)x 1st', plc)) else 0
            s = int(m.group(1)) if (m := re.search(r'(\d+)x 2nd', plc)) else 0
            b = int(m.group(1)) if (m := re.search(r'(\d+)x 3rd', plc)) else 0
            pt = float(m.group(1)) if (m := re.search(r'([\d.]+)', pts_str)) else 0.0
            if (g + s + b) > 0 or pt > 0:
                player_trophies[p]['gold'] += g
                player_trophies[p]['silver'] += s
                player_trophies[p]['bronze'] += b
                player_trophies[p]['points'] += pt
    except Exception:
        pass

    # 2. Secondary: fallback to hall_of_fame_fallback.json bundled in repo
    if not player_trophies:
        fb_path = Path(__file__).resolve().parent / "hall_of_fame_fallback.json"
        if fb_path.exists():
            try:
                with open(fb_path, 'r', encoding='utf-8') as f:
                    fb_data = json.load(f).get('international', [])
                for item in fb_data:
                    p = item['player']
                    player_trophies[p]['gold'] += item.get('gold', 0)
                    player_trophies[p]['silver'] += item.get('silver', 0)
                    player_trophies[p]['bronze'] += item.get('bronze', 0)
                    player_trophies[p]['points'] += item.get('points', 0.0)
            except Exception:
                pass

    # 3. Tertiary: Fallback to Hall of Fame.xlsx if database and JSON were unavailable
    if not player_trophies:
        hof_path = Path("data/tournaments/Hall of Fame.xlsx")
        if pd is not None and hof_path.exists():
            try:
                xl = pd.ExcelFile(hof_path)
                if 'International Championship' in xl.sheet_names:
                    df = xl.parse('International Championship')
                    for _, row in df.iterrows():
                        p = row.get('Player')
                        if pd.isna(p) or not str(p).strip() or str(p).startswith('Player') or str(p).startswith('Season') or 'ordered by' in str(p) or '*' in str(p):
                            continue
                        p = str(p).strip()
                        gold = int(row['Winner']) if pd.notna(row['Winner']) else 0
                        silver = int(row['Runner-up']) if pd.notna(row['Runner-up']) else 0
                        bronze = int(row['3rd place']) if pd.notna(row['3rd place']) else 0
                        pts = float(row['Points']) if pd.notna(row['Points']) else 0.0
                        if (gold + silver + bronze) > 0 or pts > 0:
                            player_trophies[p]['gold'] += gold
                            player_trophies[p]['silver'] += silver
                            player_trophies[p]['bronze'] += bronze
                            player_trophies[p]['points'] += pts
            except Exception:
                pass

    trophyboard = []
    for p, stats in player_trophies.items():
        tot = stats['gold'] + stats['silver'] + stats['bronze']
        if tot > 0:
            trophyboard.append({
                'player': p,
                'gold': stats['gold'],
                'silver': stats['silver'],
                'bronze': stats['bronze'],
                'total': tot,
                'points': stats['points'],
                'title': 'WC' if p in ['a440', 'Martin_Pecheur', 'Weidenbaum'] else ('GM' if stats['gold'] > 0 else 'M')
            })

    trophyboard.sort(key=lambda x: (x['gold'], x['silver'], x['bronze'], x['points']), reverse=True)
    return season_podiums, trophyboard


def derive_world_championship_trophyboard(conn) -> List[Dict[str, Any]]:
    """Returns official World Championship historical podium records."""
    return [
        {'player': 'a440', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 100.0, 'title': 'WC', 'year': '2025 World Champion'},
        {'player': 'Martin_Pecheur', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 100.0, 'title': 'WC', 'year': '2024 World Champion'},
        {'player': 'Weidenbaum', 'gold': 1, 'silver': 0, 'bronze': 0, 'total': 1, 'points': 100.0, 'title': 'WC', 'year': '2023 World Champion'},
        {'player': 'Grozz', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 50.0, 'title': 'GM', 'year': '2025 Vice-Champion'},
        {'player': 'frotes', 'gold': 0, 'silver': 1, 'bronze': 0, 'total': 1, 'points': 50.0, 'title': 'GM', 'year': '2024 Vice-Champion'},
        {'player': 'silent_x111', 'gold': 0, 'silver': 0, 'bronze': 1, 'total': 1, 'points': 25.0, 'title': 'GM', 'year': '2025 3rd Place'},
    ]


def derive_grand_slams_trophyboard(conn) -> List[Dict[str, Any]]:
    """Derives trophyboard dynamically for Grand Slams & Championship Cups directly from match records."""
    trophies = defaultdict(lambda: {'gold': 0, 'silver': 0, 'bronze': 0, 'cups': []})

    # 1. Survivors Cup 2026 Finals (3-player survival table)
    sc_final = conn.execute("""
        SELECT player1, score1, player2, score2, player3, score3
        FROM matches
        WHERE tournament LIKE '%Survivors Cup%Final%'
        ORDER BY date DESC LIMIT 1
    """).fetchone()
    if sc_final:
        plist = [(sc_final['player1'], sc_final['score1']), (sc_final['player2'], sc_final['score2']), (sc_final['player3'], sc_final['score3'])]
        plist = sorted([(p, float(sc) if sc is not None else 0.0) for p, sc in plist if p], key=lambda x: x[1], reverse=True)
        if len(plist) >= 1:
            trophies[plist[0][0]]['gold'] += 1
            trophies[plist[0][0]]['cups'].append('2026 Survivors Cup Champion')
        if len(plist) >= 2:
            trophies[plist[1][0]]['silver'] += 1
            trophies[plist[1][0]]['cups'].append('2026 Survivors Cup Runner-Up')
        if len(plist) >= 3:
            trophies[plist[2][0]]['bronze'] += 1
            trophies[plist[2][0]]['cups'].append('2026 Survivors Cup 3rd Place')

    # 2. Slow Burn Season 15 Finals (3-match endurance series)
    sb_rows = conn.execute("""
        SELECT player1, score1, player2, score2, player3, score3
        FROM matches
        WHERE tournament LIKE '%Slow Burn%Final%'
    """).fetchall()
    if sb_rows:
        sb_scores = defaultdict(float)
        sb_wins = defaultdict(int)
        for r in sb_rows:
            plist = [(r['player1'], r['score1']), (r['player2'], r['score2']), (r['player3'], r['score3'])]
            plist = sorted([(p, float(sc) if sc is not None else 0.0) for p, sc in plist if p], key=lambda x: x[1], reverse=True)
            if plist:
                sb_wins[plist[0][0]] += 1
                for p, sc in plist:
                    sb_scores[p] += sc
        sorted_sb = sorted(sb_scores.keys(), key=lambda p: (sb_wins[p], sb_scores[p]), reverse=True)
        if len(sorted_sb) >= 1:
            trophies[sorted_sb[0]]['gold'] += 1
            trophies[sorted_sb[0]]['cups'].append('Slow Burn S15 Champion')
        if len(sorted_sb) >= 2:
            trophies[sorted_sb[1]]['silver'] += 1
            trophies[sorted_sb[1]]['cups'].append('Slow Burn S15 Runner-Up')
        if len(sorted_sb) >= 3:
            trophies[sorted_sb[2]]['bronze'] += 1
            trophies[sorted_sb[2]]['cups'].append('Slow Burn S15 3rd Place')

    # 3. Wimbledon TTA (2023 & 2025 Editions)
    # 2023 Finals (Stage 7 - 5 games)
    wimb_23 = conn.execute("""
        SELECT player1, score1, player2, score2
        FROM matches
        WHERE tournament LIKE 'Wimbledon 2023 stage 7%'
    """).fetchall()
    if wimb_23:
        w23_wins = defaultdict(int)
        for r in wimb_23:
            s1, s2 = float(r['score1'] or 0), float(r['score2'] or 0)
            if s1 > s2: w23_wins[r['player1']] += 1
            elif s2 > s1: w23_wins[r['player2']] += 1
        sorted_w23 = sorted(w23_wins.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_w23) >= 1:
            trophies[sorted_w23[0][0]]['gold'] += 1
            trophies[sorted_w23[0][0]]['cups'].append('2023 Wimbledon TTA Champion')
        if len(sorted_w23) >= 2:
            trophies[sorted_w23[1][0]]['silver'] += 1
            trophies[sorted_w23[1][0]]['cups'].append('2023 Wimbledon TTA Runner-Up')

    # 2025 Finals (Stage 10 - Round Robin)
    wimb_25 = conn.execute("""
        SELECT player1, score1, player2, score2
        FROM matches
        WHERE tournament LIKE 'Wimbledon 2025 Stage 10%'
    """).fetchall()
    if wimb_25:
        w25_wins = defaultdict(int)
        w25_pts = defaultdict(float)
        for r in wimb_25:
            p1, s1 = r['player1'], float(r['score1'] or 0)
            p2, s2 = r['player2'], float(r['score2'] or 0)
            w25_pts[p1] += s1; w25_pts[p2] += s2
            if s1 > s2: w25_wins[p1] += 1
            elif s2 > s1: w25_wins[p2] += 1
        sorted_w25 = sorted(w25_wins.keys(), key=lambda p: (w25_wins[p], w25_pts[p]), reverse=True)
        if len(sorted_w25) >= 1:
            trophies[sorted_w25[0]]['gold'] += 1
            trophies[sorted_w25[0]]['cups'].append('2025 Wimbledon TTA Champion')
        if len(sorted_w25) >= 2:
            trophies[sorted_w25[1]]['silver'] += 1
            trophies[sorted_w25[1]]['cups'].append('2025 Wimbledon TTA Runner-Up')
        if len(sorted_w25) >= 3:
            trophies[sorted_w25[2]]['bronze'] += 1
            trophies[sorted_w25[2]]['cups'].append('2025 Wimbledon TTA 3rd Place')

    # 4. Eiffel Tower "The Top" Peak Competitors
    eiffel_top = conn.execute("""
        SELECT player1, score1, player2, score2, player3, score3, player4, score4, player_count
        FROM matches
        WHERE tournament LIKE '%Eiffel Tower%The Top%'
    """).fetchall()
    e_wins = defaultdict(int)
    for r in eiffel_top:
        p_cnt = r['player_count']
        plist = [(r[f'player{i}'], r[f'score{i}']) for i in range(1, p_cnt + 1) if r[f'player{i}'] and r[f'score{i}'] is not None]
        plist = sorted([(p, float(sc)) for p, sc in plist], key=lambda x: x[1], reverse=True)
        if plist:
            e_wins[plist[0][0]] += 1
    for p, w in sorted(e_wins.items(), key=lambda x: x[1], reverse=True)[:3]:
        trophies[p]['gold'] += 1
        trophies[p]['cups'].append(f'Eiffel Tower Pinnacle Champion ({w} Top Victories)')

    gs_board = []
    for p, stats in trophies.items():
        tot = stats['gold'] + stats['silver'] + stats['bronze']
        if tot > 0:
            gs_board.append({
                'player': p,
                'gold': stats['gold'],
                'silver': stats['silver'],
                'bronze': stats['bronze'],
                'total': tot,
                'details': ", ".join(stats['cups'][:2])
            })
    gs_board.sort(key=lambda x: (x['gold'], x['silver'], x['bronze'], x['total']), reverse=True)
    return gs_board


def derive_ladders_trophyboard(conn) -> List[Dict[str, Any]]:
    """Derives trophyboard for all continuous competitive ladders (Mercurial, Sodium, TCL)."""
    ladder_matches = conn.execute("""
        SELECT tournament, player_count, player1, score1, player2, score2, player3, score3, player4, score4
        FROM matches
        WHERE tournament LIKE '%Mercurial%' OR tournament LIKE '%Sodium%' OR tournament LIKE '%TCL%'
    """).fetchall()

    ladder_wins = defaultdict(lambda: {'wins': 0, 'matches': 0, 'tourneys': set()})
    for r in ladder_matches:
        p_cnt = r['player_count']
        plist = [(r['player1'], r['score1']), (r['player2'], r['score2']), (r['player3'], r['score3']), (r['player4'], r['score4'])][:p_cnt]
        plist = sorted([(p, float(sc) if sc is not None else 0.0) for p, sc in plist if p], key=lambda x: x[1], reverse=True)
        if not plist: continue

        for p, _ in plist:
            ladder_wins[p]['matches'] += 1
            ladder_wins[p]['tourneys'].add(r['tournament'][:15])
        ladder_wins[plist[0][0]]['wins'] += 1

    ladder_board = []
    for p, stats in ladder_wins.items():
        if stats['matches'] >= 30:
            wr = round(100.0 * stats['wins'] / stats['matches'], 1)
            ladder_board.append({
                'player': p,
                'matches': stats['matches'],
                'wins': stats['wins'],
                'win_rate': wr,
                'circuits': len(stats['tourneys'])
            })
    ladder_board.sort(key=lambda x: (x['wins'], x['win_rate']), reverse=True)
    return ladder_board[:15]


def sync_tournament_achievements(conn: sqlite3.Connection) -> None:
    """Calculates all tournament results and saves verified counts directly into player_achievements in SQLite."""
    _, rl_board = derive_royal_league_podiums(conn)
    _, im_board = derive_intermezzo_podiums(conn)
    _, ic_board = derive_international_podiums(conn)
    wc_board = derive_world_championship_trophyboard(conn)

    player_stats = defaultdict(lambda: {
        'world_titles': 0,
        'intl_titles': 0,
        'inter_titles': 0,
        'rl_titles': 0,
        'other_titles': 0,
        'world_gold': 0, 'world_silver': 0, 'world_bronze': 0,
        'intl_gold': 0, 'intl_silver': 0, 'intl_bronze': 0,
        'inter_gold': 0, 'inter_silver': 0, 'inter_bronze': 0,
        'rl_gold': 0, 'rl_silver': 0, 'rl_bronze': 0,
        'achievements': []
    })

    # 1. World Championships
    for item in wc_board:
        p = item['player']
        if item['gold'] > 0:
            player_stats[p]['world_titles'] += item['gold']
            player_stats[p]['world_gold'] += item['gold']
            player_stats[p]['achievements'].append(item.get('year', 'World Champion'))
        if item['silver'] > 0:
            player_stats[p]['world_silver'] += item['silver']
            player_stats[p]['achievements'].append(item.get('year', 'WCS Finalist'))
        if item['bronze'] > 0:
            player_stats[p]['world_bronze'] += item['bronze']

    # 2. International Championship
    for item in ic_board:
        p = item['player']
        player_stats[p]['intl_titles'] += item['gold']
        player_stats[p]['intl_gold'] += item['gold']
        player_stats[p]['intl_silver'] += item['silver']
        player_stats[p]['intl_bronze'] += item['bronze']
        if item['gold'] > 0:
            player_stats[p]['achievements'].append(f"{item['gold']}x International Champion")

    # 3. Intermezzo Championship
    for item in im_board:
        p = item['player']
        player_stats[p]['inter_titles'] += item['gold']
        player_stats[p]['inter_gold'] += item['gold']
        player_stats[p]['inter_silver'] += item['silver']
        player_stats[p]['inter_bronze'] += item['bronze']
        if item['gold'] > 0:
            player_stats[p]['achievements'].append(f"{item['gold']}x Intermezzo Champion")

    # 4. Royal League (Emperor)
    for item in rl_board:
        p = item['player']
        player_stats[p]['rl_titles'] += item['gold']
        player_stats[p]['rl_gold'] += item['gold']
        player_stats[p]['rl_silver'] += item['silver']
        player_stats[p]['rl_bronze'] += item['bronze']
        if item['gold'] > 0:
            player_stats[p]['achievements'].append(f"{item['gold']}x Royal League Emperor Champion")

    # Clean write to database
    with conn:
        conn.execute("DELETE FROM player_achievements")
        for p, st in player_stats.items():
            tot_titles = st['world_titles'] + st['intl_titles'] + st['inter_titles'] + st['rl_titles']
            gold = st['world_gold'] + st['intl_gold'] + st['inter_gold'] + st['rl_gold']
            silver = st['world_silver'] + st['intl_silver'] + st['inter_silver'] + st['rl_silver']
            bronze = st['world_bronze'] + st['intl_bronze'] + st['inter_bronze'] + st['rl_bronze']
            tot_medals = gold + silver + bronze

            if tot_titles == 0 and tot_medals == 0:
                continue

            summary_parts = []
            if st['world_titles']: summary_parts.append(f"{st['world_titles']}x World Champion")
            if st['intl_titles']: summary_parts.append(f"{st['intl_titles']}x International Champion")
            if st['inter_titles']: summary_parts.append(f"{st['inter_titles']}x Intermezzo Champion")
            if st['rl_titles']: summary_parts.append(f"{st['rl_titles']}x Royal League Champion")
            
            summary_text = f"{p} is a decorated competitor with " + ", ".join(summary_parts) + f" (Total Career Medals: {gold}G / {silver}S / {bronze}B)." if summary_parts else f"{p} has achieved {gold}G / {silver}S / {bronze}B podium medals."

            conn.execute("""
                INSERT OR REPLACE INTO player_achievements (
                    player_name, total_titles, world_titles, international_titles,
                    intermezzo_titles, royal_league_titles, other_titles,
                    gold_medals, silver_medals, bronze_medals, summary_text, top_achievements_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p, tot_titles, st['world_titles'], st['intl_titles'], st['inter_titles'],
                st['rl_titles'], st['other_titles'], gold, silver, bronze,
                summary_text, json.dumps(st['achievements'][:6])
            ))


def get_premier_single_game_records_with_opponents(series_slug: str, db_path: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches premier division highest single-match culture scores along with opponent names and scores."""
    conn = get_connection(db_path)
    try:
        if series_slug == 'royal_league':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
                FROM matches
                WHERE (tournament LIKE 'RL_%' OR tournament LIKE '%Royal League%')
                  AND tournament LIKE '%Emperor%'
            """
        elif series_slug == 'international':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
                FROM matches
                WHERE tournament LIKE 'International%'
                  AND (tournament LIKE '%Grandmaster%' OR tournament LIKE '%Diamond%')
                  AND tournament NOT LIKE '%Master 1%'
                  AND tournament NOT LIKE '%Master 2%'
            """
        elif series_slug == 'intermezzo':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
                FROM matches
                WHERE tournament LIKE 'Intermezzo%'
                  AND (tournament LIKE '%Grandmaster%' OR tournament LIKE '%GM%' OR tournament LIKE '%Diamond%' OR tournament LIKE '%Premier%')
                  AND tournament NOT LIKE '%Master 1%'
                  AND tournament NOT LIKE '%Master 2%'
            """
        elif series_slug == 'worlds':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
                FROM matches
                WHERE (tournament LIKE '%World%' OR tournament LIKE '%Worlds%')
                  AND (tournament LIKE '%Stage 4%' OR tournament LIKE '%Final%' OR tournament LIKE '%Upper%' OR tournament LIKE '%Lower%')
            """
        else:
            return []

        rows = conn.execute(query).fetchall()
        records = []
        for r in rows:
            p_cnt = r['player_count']
            participants = []
            for i in range(1, p_cnt + 1):
                p = r[f'player{i}']
                sc = r[f'score{i}']
                if p and sc is not None:
                    participants.append((p, float(sc)))

            if not participants:
                continue
            participants.sort(key=lambda x: x[1], reverse=True)

            winner_p, winner_sc = participants[0]
            opponents = participants[1:]
            opp_str = ", ".join([f"{op_p} ({int(op_sc) if op_sc.is_integer() else op_sc} pts)" for op_p, op_sc in opponents])

            records.append({
                'player': winner_p,
                'score': winner_sc,
                'opponents_display': opp_str,
                'tournament': r['tournament'],
                'date': r['date']
            })

        records.sort(key=lambda x: x['score'], reverse=True)
        return records[:limit]
    finally:
        conn.close()


def get_premier_seasonal_records(series_slug: str, db_path: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Calculates all-time highest seasonal league points achieved in premier divisions."""
    conn = get_connection(db_path)
    try:
        if series_slug == 'royal_league':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2
                FROM matches
                WHERE (tournament LIKE 'RL_%' OR tournament LIKE '%Royal League%')
                  AND tournament LIKE '%Emperor%'
            """
        elif series_slug == 'international':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3, player4, score4
                FROM matches
                WHERE tournament LIKE 'International%'
                  AND (tournament LIKE '%Grandmaster%' OR tournament LIKE '%Diamond%')
                  AND tournament NOT LIKE '%Master 1%'
                  AND tournament NOT LIKE '%Master 2%'
            """
        elif series_slug == 'intermezzo':
            query = """
                SELECT tournament, date, player_count, player1, score1, player2, score2, player3, score3
                FROM matches
                WHERE tournament LIKE 'Intermezzo%'
                  AND (tournament LIKE '%Grandmaster%' OR tournament LIKE '%GM%' OR tournament LIKE '%Diamond%' OR tournament LIKE '%Premier%')
                  AND tournament NOT LIKE '%Master 1%'
                  AND tournament NOT LIKE '%Master 2%'
            """
        else:
            return []

        rows = conn.execute(query).fetchall()
        campaigns = defaultdict(lambda: {
            'pts': 0.0, 'games': 0,
            'p1': 0, 'p2': 0, 'p3': 0, 'p4': 0,
            'w': 0, 'd': 0, 'l': 0,
            'date': '', 'div': ''
        })

        for r in rows:
            t = r['tournament']
            p_cnt = r['player_count']
            plist = []
            for i in range(1, p_cnt + 1):
                p = r[f'player{i}']
                sc = r[f'score{i}']
                if p and sc is not None:
                    plist.append((p, float(sc)))
            plist.sort(key=lambda x: x[1], reverse=True)
            if not plist:
                continue

            m = re.search(r'S0?(\d+)', t, re.I) or re.search(r's0?(\d+)', t, re.I)
            season_key = f"Season {m.group(1)}" if m else "Season"
            div_name = "Emperor" if series_slug == 'royal_league' else "Grandmaster"

            if series_slug == 'royal_league':
                p1, sc1 = plist[0]
                p2, sc2 = plist[1] if len(plist) > 1 else ('', 0.0)
                if not p1 or not p2:
                    continue
                c1, c2 = campaigns[(season_key, p1)], campaigns[(season_key, p2)]
                c1['games'] += 1; c2['games'] += 1
                c1['date'] = r['date']; c2['date'] = r['date']
                c1['div'] = div_name; c2['div'] = div_name
                if sc1 > sc2:
                    c1['pts'] += 2.0; c1['w'] += 1; c2['l'] += 1
                elif sc2 > sc1:
                    c2['pts'] += 2.0; c2['w'] += 1; c1['l'] += 1
                else:
                    c1['pts'] += 1.0; c2['pts'] += 1.0
                    c1['d'] += 1; c2['d'] += 1
            elif series_slug == 'intermezzo':
                for rank, (p, sc) in enumerate(plist, 1):
                    c = campaigns[(season_key, p)]
                    c['games'] += 1; c['date'] = r['date']; c['div'] = div_name
                    if rank == 1:
                        c['pts'] += 5.0; c['p1'] += 1
                    elif rank == 2:
                        c['pts'] += 2.0; c['p2'] += 1
                    elif rank == 3:
                        c['p3'] += 1
            elif series_slug == 'international':
                for rank, (p, sc) in enumerate(plist, 1):
                    c = campaigns[(season_key, p)]
                    c['games'] += 1; c['date'] = r['date']; c['div'] = div_name
                    if rank == 1:
                        c['pts'] += (6.0 if p_cnt == 4 else 5.0)
                        c['p1'] += 1
                    elif rank == 2:
                        c['pts'] += (3.0 if p_cnt == 4 else 2.0)
                        c['p2'] += 1
                    elif rank == 3:
                        if p_cnt == 4:
                            c['pts'] += 1.0
                        c['p3'] += 1
                    elif rank == 4:
                        c['p4'] += 1

        min_games = 5 if series_slug == 'royal_league' else 6
        records = []
        for (s_key, p), data in campaigns.items():
            if data['games'] >= min_games:
                if series_slug == 'royal_league':
                    rec_display = f"{data['w']}/{data['l']}" if data['d'] == 0 else f"{data['w']}/{data['d']}/{data['l']}"
                    wins = data['w']
                    seconds = data['d']
                elif series_slug == 'intermezzo':
                    rec_display = f"{data['p1']}/{data['p2']}/{data['p3']}"
                    wins = data['p1']
                    seconds = data['p2']
                else:  # international
                    rec_display = f"{data['p1']}/{data['p2']}/{data['p3']}/{data['p4']}"
                    wins = data['p1']
                    seconds = data['p2']

                records.append({
                    'player': p,
                    'season': s_key,
                    'division': data['div'],
                    'points': data['pts'],
                    'games': data['games'],
                    'wins': wins,
                    'second_places': seconds,
                    'record_display': rec_display,
                    'date': data['date']
                })

        records.sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        return records[:limit]
    finally:
        conn.close()


_HOF_CACHE: Optional[Dict[str, Any]] = None


def clear_hof_cache():
    """Invalidates the in-memory Hall of Fame cache."""
    global _HOF_CACHE
    _HOF_CACHE = None


def derive_series_live_metrics(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Derives exact match totals, season counts, and active ranges dynamically from database match history."""
    cur = conn.cursor()

    # 1. International
    intl_m = cur.execute("SELECT COUNT(*) FROM matches WHERE tournament LIKE 'International%'").fetchone()[0] or 0
    intl_seasons = [
        int(m.group(1))
        for (t,) in cur.execute("SELECT DISTINCT tournament FROM matches WHERE tournament LIKE 'International%'").fetchall()
        if t and (m := re.search(r'S(\d+)', t, re.I))
    ]
    intl_max = max(intl_seasons) if intl_seasons else 34

    # 2. Intermezzo
    inter_m = cur.execute("SELECT COUNT(*) FROM matches WHERE tournament LIKE 'Intermezzo%'").fetchone()[0] or 0
    inter_seasons = [
        int(m.group(1))
        for (t,) in cur.execute("SELECT DISTINCT tournament FROM matches WHERE tournament LIKE 'Intermezzo%'").fetchall()
        if t and (m := re.search(r'S(\d+)', t, re.I))
    ]
    inter_max = max(inter_seasons) if inter_seasons else 30

    # 3. Royal League
    rl_m = cur.execute("SELECT COUNT(*) FROM matches WHERE tournament LIKE 'RL_%' OR tournament LIKE '%Royal League%'").fetchone()[0] or 0
    rl_seasons = [
        int(m.group(1))
        for (t,) in cur.execute("SELECT DISTINCT tournament FROM matches WHERE tournament LIKE 'RL_%' OR tournament LIKE '%Royal League%'").fetchall()
        if t and (m := re.search(r's0?(\d+)', t, re.I))
    ]
    rl_max = max(rl_seasons) if rl_seasons else 9

    # 4. World Championship
    wcs_m = cur.execute("SELECT COUNT(*) FROM matches WHERE tournament LIKE '%World%' OR tournament LIKE '%Worlds%'").fetchone()[0] or 0
    wcs_editions = set()
    for (t,) in cur.execute("SELECT DISTINCT tournament FROM matches WHERE tournament LIKE '%World%' OR tournament LIKE '%Worlds%'").fetchall():
        if t:
            m = re.search(r'Worlds?\s*(\d+)', t, re.I) or re.search(r'202\d', t)
            if m:
                wcs_editions.add(m.group(0))
    wcs_count = len(wcs_editions) if wcs_editions else 4

    # 5. Grand Slams & Championship Cups
    gs_m = cur.execute("""
        SELECT COUNT(*) FROM matches
        WHERE tournament LIKE '%Survivor%' OR tournament LIKE '%Slam%' OR tournament LIKE '%Eiffel%'
           OR tournament LIKE '%Wimbledon%' OR tournament LIKE '%Slow Burn%' OR tournament LIKE 'Australian Open%'
           OR tournament LIKE 'French Open%'
    """).fetchone()[0] or 0
    gs_tourneys = {
        t.split('Stage')[0].strip()
        for (t,) in cur.execute("""
            SELECT DISTINCT tournament FROM matches
            WHERE tournament LIKE '%Survivor%' OR tournament LIKE '%Slam%' OR tournament LIKE '%Eiffel%'
               OR tournament LIKE '%Wimbledon%' OR tournament LIKE '%Slow Burn%' OR tournament LIKE 'Australian Open%'
               OR tournament LIKE 'French Open%'
        """).fetchall()
        if t
    }
    gs_count = len(gs_tourneys) if gs_tourneys else 6

    # 6. Ladders
    ladder_m = cur.execute("""
        SELECT COUNT(*) FROM matches
        WHERE tournament LIKE '%Mercurial%' OR tournament LIKE '%Sodium%' OR tournament LIKE '%TCL%' OR tournament LIKE 'ML_%'
    """).fetchone()[0] or 0

    return {
        'international': {
            'total_matches': intl_m,
            'seasons_count': intl_max,
            'active_range': f"2016 – Present (Current: Season {intl_max})"
        },
        'intermezzo': {
            'total_matches': inter_m,
            'seasons_count': inter_max,
            'active_range': f"2018 – Present (Current: Season {inter_max})"
        },
        'royal_league': {
            'total_matches': rl_m,
            'seasons_count': rl_max,
            'active_range': f"2024 – Present (Current: Season {rl_max})"
        },
        'worlds': {
            'total_matches': wcs_m,
            'seasons_count': wcs_count,
            'active_range': f"2023 – Present (Next: 2027)"
        },
        'grand_slams': {
            'total_matches': gs_m,
            'seasons_count': gs_count,
            'active_range': "2023 – Present"
        },
        'ladders': {
            'total_matches': ladder_m,
            'seasons_count': 16,
            'active_range': "2017 – Present"
        }
    }


def derive_hall_of_fame_data(db_path: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """Builds complete Hall of Fame datasets with in-memory memoization."""
    global _HOF_CACHE
    if not force_refresh and _HOF_CACHE is not None and db_path is None:
        return _HOF_CACHE

    conn = get_connection(db_path)
    try:
        # 1. Derive Major Circuits Trophyboards (SQLite primary -> fallback JSON -> Excel)
        rl_podiums, rl_board = derive_royal_league_podiums(conn)
        im_podiums, im_board = derive_intermezzo_podiums(conn)
        ic_podiums, ic_board = derive_international_podiums(conn)
        wc_board = derive_world_championship_trophyboard(conn)

        # 2. Derive Grand Slams & Ladders Trophyboards
        gs_board = derive_grand_slams_trophyboard(conn)
        ladder_board = derive_ladders_trophyboard(conn)

        # 3. Synchronize player_achievements table if empty, underpopulated, or forced
        ach_count = conn.execute("SELECT COUNT(*) FROM player_achievements").fetchone()[0]
        max_titles = conn.execute("SELECT MAX(total_titles) FROM player_achievements").fetchone()[0] or 0
        if ach_count < 30 or max_titles < 10 or force_refresh:
            sync_tournament_achievements(conn)

        # 4. Construct All-Time Major Legends directly from the 4 verified trophyboards
        legends = defaultdict(lambda: {
            'world_titles': 0, 'intl_titles': 0, 'inter_titles': 0,
            'rl_titles': 0, 'gold': 0, 'silver': 0, 'bronze': 0,
            'top_achievements': []
        })

        for x in wc_board:
            p = x['player']
            legends[p]['world_titles'] += x.get('gold', 0)
            legends[p]['gold'] += x.get('gold', 0)
            legends[p]['silver'] += x.get('silver', 0)
            legends[p]['bronze'] += x.get('bronze', 0)
            if x.get('gold', 0) > 0:
                legends[p]['top_achievements'].append(x.get('year', 'World Champion'))

        for x in ic_board:
            p = x['player']
            legends[p]['intl_titles'] += x.get('gold', 0)
            legends[p]['gold'] += x.get('gold', 0)
            legends[p]['silver'] += x.get('silver', 0)
            legends[p]['bronze'] += x.get('bronze', 0)
            if x.get('gold', 0) > 0:
                legends[p]['top_achievements'].append(f"{x['gold']}x International Champion")

        for x in im_board:
            p = x['player']
            legends[p]['inter_titles'] += x.get('gold', 0)
            legends[p]['gold'] += x.get('gold', 0)
            legends[p]['silver'] += x.get('silver', 0)
            legends[p]['bronze'] += x.get('bronze', 0)
            if x.get('gold', 0) > 0:
                legends[p]['top_achievements'].append(f"{x['gold']}x Intermezzo Champion")

        for x in rl_board:
            p = x['player']
            legends[p]['rl_titles'] += x.get('gold', 0)
            legends[p]['gold'] += x.get('gold', 0)
            legends[p]['silver'] += x.get('silver', 0)
            legends[p]['bronze'] += x.get('bronze', 0)
            if x.get('gold', 0) > 0:
                legends[p]['top_achievements'].append(f"{x['gold']}x Royal League Emperor Champion")

        all_time_major_legends = []
        for p, st in legends.items():
            tot_titles = st['world_titles'] + st['intl_titles'] + st['inter_titles'] + st['rl_titles']
            tot_medals = st['gold'] + st['silver'] + st['bronze']
            if tot_titles > 0 or tot_medals >= 2:
                all_time_major_legends.append({
                    'player': p,
                    'total_titles': tot_titles,
                    'world_titles': st['world_titles'],
                    'intl_titles': st['intl_titles'],
                    'inter_titles': st['inter_titles'],
                    'rl_titles': st['rl_titles'],
                    'gold': st['gold'],
                    'silver': st['silver'],
                    'bronze': st['bronze'],
                    'total_medals': tot_medals,
                    'top_achievements': st['top_achievements'][:3]
                })

        all_time_major_legends.sort(
            key=lambda x: (x['total_titles'], x['world_titles'], x['gold'], x['silver'], x['bronze'], x['total_medals']),
            reverse=True
        )

        series_metrics = derive_series_live_metrics(conn)

        result = {
            'rl_board': rl_board,
            'im_board': im_board,
            'ic_board': ic_board,
            'wc_board': wc_board,
            'gs_board': gs_board,
            'ladder_board': ladder_board,
            'all_time_major_legends': all_time_major_legends[:25],
            'series_metrics': series_metrics,
            'metrics': {
                'intl_matches': series_metrics['international']['total_matches'],
                'inter_matches': series_metrics['intermezzo']['total_matches'],
                'rl_matches': series_metrics['royal_league']['total_matches'],
                'wcs_matches': series_metrics['worlds']['total_matches'],
                'gs_matches': series_metrics['grand_slams']['total_matches'],
            }
        }
        if db_path is None:
            _HOF_CACHE = result
        return result
    finally:
        conn.close()

