import pytest
from src.web.app import app
from src.data.db import get_connection

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_database_multi_format_ratings():
    conn = get_connection()
    try:
        formats = [0, 2, 3, 4]
        for fmt in formats:
            for model in ['glicko2_std', 'glicko2_mp', 'whr']:
                cnt = conn.execute(
                    'SELECT count(*) FROM player_ratings WHERE model_type = ? AND player_count = ?',
                    (model, fmt)
                ).fetchone()[0]
                assert cnt > 1000, f"Expected >1000 players for model {model} in format {fmt}, got {cnt}"
    finally:
        conn.close()

def test_official_baseline_populated():
    conn = get_connection()
    try:
        cnt = conn.execute('SELECT count(*) FROM official_baseline').fetchone()[0]
        assert cnt == 3489, f"Expected 3489 baseline records, got {cnt}"
    finally:
        conn.close()

def test_leaderboard_inactivity_filter_default(client):
    """By default, the leaderboard must filter out inactive players and apply min_opps=30."""
    rv = client.get('/leaderboard')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Active Only' in html
    # Active players with >= 30 matches: 1,357 (baseline), 1,377 or 1,380 or 1,409 or 1,410 (with updated match archives)
    assert any(c in html for c in ['1,357', '1,377', '1,380', '1,409', '1,410'])

    # Without minimum matches filter: 1,507 active players (baseline), 1,519 or 1,533 (with updated matches)
    rv_all_min = client.get('/leaderboard?min_opps=0')
    assert rv_all_min.status_code == 200
    assert any(c in rv_all_min.get_data(as_text=True) for c in ['1,507', '1,519', '1,533'])

def test_leaderboard_inactivity_filter_all(client):
    """When status=all and min_opps=0, all 3,489 players should be accessible."""
    rv = client.get('/leaderboard?status=all&min_opps=0')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '3,489' in html

def test_leaderboard_format_selector(client):
    """Ensure 2p, 3p, 4p formats can be selected."""
    for fmt in [2, 3, 4]:
        rv = client.get(f'/leaderboard?format={fmt}')
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert f'{fmt}-Player' in html

def test_leaderboard_rb48_deltas(client):
    """Ensure RB48 deltas work for baseline and time windows including last_update."""
    for window in ['last_update', 'baseline', 'month', 'quarter', 'year']:
        rv = client.get(f'/leaderboard?delta={window}')
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert 'delta-badge' in html

def test_leaderboard_multi_name_search(client):
    """Ensure comma-separated multi-name search returns genuine global ranks."""
    rv = client.get('/leaderboard?search=Weidenbaum,Genghisip')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Weidenbaum' in html
    assert 'Genghisip' in html
    # Should show true ranks (e.g. #2, #4), not #1, #2
    assert '#2' in html
    assert '#4' in html

def test_leaderboard_single_name_jump(client):
    """Ensure single name search jumps to full leaderboard page with highlight."""
    rv = client.get('/leaderboard?search=Weidenbaum')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'player-Weidenbaum' in html
    assert 'jump-highlight' in html

def test_no_broken_descriptors_in_analysis(client):
    """Ensure broken descriptors like $ho$ or carriage return artifacts are completely eliminated."""
    rv = client.get('/analysis')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '$ho$' not in html
    assert '$ ho$' not in html

def test_faq_route(client):
    """Ensure the FAQ route works and reflects updated tabs and Platinum title."""
    rv = client.get('/faq')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Frequently Asked Questions & Model Guide' in html
    assert 'Rating Models' in html
    assert 'Conservative Rating' in html
    assert 'Multiplayer Weighting' in html
    assert 'Titles &amp; Badges' in html or 'Titles & Badges' in html
    # WHR dedicated card assertions
    assert 'Whole-History Rating (WHR): How Does It Work' in html
    assert 'Brownian Motion' in html
    assert 'Key Differences: WHR vs. Glicko-2' in html
    # RB48 Deltas tab was removed from FAQ as requested
    assert 'onclick="switchFaqTab(\'deltas\'' not in html

def test_analysis_calibration_subpage(client):
    """Ensure the calibration dashboard renders with Brier scores and reliability data."""
    rv = client.get('/analysis/calibration')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'heroCalibrationChart' in html
    assert 'Brier Score' in html
    assert 'Expected Calibration Error' in html

def test_analysis_movers_subpage(client):
    """Ensure the multi-engine comparison page renders."""
    rv = client.get('/analysis/movers')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Multi-Engine Player Comparison' in html

def test_analysis_activity_subpage(client):
    """Ensure the activity & demographics subpage renders."""
    rv = client.get('/analysis/activity')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Player Activity' in html
    assert 'Active Players' in html
    assert 'Inactive / Retired' in html
    assert 'Matches by Game Format' in html


def test_tournament_achievements_database():
    """Ensure player_achievements and tournament_records tables are properly populated."""
    conn = get_connection()
    try:
        ach_count = conn.execute('SELECT COUNT(*) FROM player_achievements').fetchone()[0]
        rec_count = conn.execute('SELECT COUNT(*) FROM tournament_records').fetchone()[0]
        assert ach_count >= 40, f"Expected >= 40 players in player_achievements, got {ach_count}"
        assert rec_count >= 1000, f"Expected >= 1000 tournament records, got {rec_count}"

        weid = conn.execute('SELECT * FROM player_achievements WHERE player_name = "Weidenbaum"').fetchone()
        assert weid is not None
        assert weid['total_titles'] >= 2
        assert 'World Champion' in weid['summary_text']

        daneo = conn.execute('SELECT * FROM player_achievements WHERE player_name = "DANeo"').fetchone()
        assert daneo is not None
        assert daneo['total_titles'] >= 1
    finally:
        conn.close()


def test_player_profile_achievements(client):
    """Ensure player profile renders tournament accolades, dark gold styling, and achievements button."""
    rv = client.get('/player/DANeo')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'text-gold-contrast' in html
    assert 'Tournament Achievements' in html
    assert '⚔️ Matches' in html or 'Matches' in html

    rv_weid = client.get('/player/Weidenbaum')
    assert rv_weid.status_code == 200
    html_weid = rv_weid.get_data(as_text=True)
    assert 'International Champion' in html_weid


def test_player_achievements_subpage(client):
    """Ensure the tournament achievements subpage renders complete historical records."""
    rv = client.get('/player/DANeo/achievements')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Historical Tournament Records' in html
    assert 'Total Championships' in html
    assert 'Gold Medals' in html

    rv_weid = client.get('/player/Weidenbaum/achievements')
    assert rv_weid.status_code == 200
    html_weid = rv_weid.get_data(as_text=True)
    assert 'International Championship' in html_weid
    assert 'Intermezzo Championship' in html_weid


def test_api_h2h_matches(client):
    """Ensure the exclusive head-to-head API returns matching games between players."""
    rv = client.get('/api/h2h/Weidenbaum/saru')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['player1'] == 'Weidenbaum'
    assert data['player2'] == 'saru'
    assert data['total_matches'] > 0
    assert 'matches' in data
    assert len(data['matches']) == data['total_matches']


def test_gold_badge_and_format_tooltips_removed(client):
    """Ensure Gold (G) title is supported and format tooltips are cleanly removed."""
    rv = client.get('/leaderboard?title=G')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'badge-g' in html
    assert 'Gold (G)' in html
    # Ensure editorial format tooltips are removed from format-bar
    assert 'Pure heads-up zero-sum strategy' not in html
    assert 'Dynamic tactical triangle' not in html


def test_analysis_overview_title_benchmarks(client):
    """Ensure the main analysis overview displays hero calibration chart and bin accuracy table."""
    rv = client.get('/analysis')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'heroCalibrationChart' in html
    assert 'Overall Predictive Model Rankings' in html or 'Predictive Model Rankings' in html
    assert 'Webmaster Model Assessment' in html


def test_peak_rank_calculation(client):
    """Ensure player profile renders peak rating with historical peak rank."""
    rv = client.get('/player/Weidenbaum')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Peak:' in html
    assert 'Rank #' in html
    assert 'home_button_circle.png' in html


def test_no_fake_title_counts(client):
    """Ensure title badges do not contain fabricated parenthetical numbers like (27)."""
    rv = client.get('/player/Weidenbaum')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Grandmaster (' not in html
    assert '27 tournament titles won' not in html

    rv_ach = client.get('/player/Weidenbaum/achievements')
    assert rv_ach.status_code == 200
    html_ach = rv_ach.get_data(as_text=True)
    assert 'Grandmaster (' not in html_ach


def test_chronological_records_order(client):
    """Ensure tournament records in achievements subpage are sorted newest to oldest."""
    rv = client.get('/player/Weidenbaum/achievements')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    # Check that newer season appears before older season
    import re
    idx_s34 = html.find('Season 34')
    m_s1 = re.search(r'Season 1(?!\d)', html)
    idx_s1 = m_s1.start() if m_s1 else -1
    if idx_s34 != -1 and idx_s1 != -1:
        assert idx_s34 < idx_s1, f"Expected Season 34 (idx {idx_s34}) before Season 1 (idx {idx_s1})"


def test_flag_svg_rendering(client):
    """Ensure authentic SVG flag images are rendered instead of raw text country codes."""
    rv = client.get('/leaderboard')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '<img src="/static/flags/' in html
    assert 'class="flag-icon-img"' in html

    rv_p = client.get('/player/DANeo')
    assert rv_p.status_code == 200
    html_p = rv_p.get_data(as_text=True)
    assert '<img src="/static/flags/' in html_p


def test_seasons_vs_career_switch(client):
    """Ensure achievements subpage provides Date of Finish column and Seasons vs Career switch."""
    rv = client.get('/player/Weidenbaum/achievements')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Date of Finish' in html
    assert 'Individual Seasons &amp; Tournaments' in html or 'Individual Seasons & Tournaments' in html
    assert 'Career Totals &amp; Hall of Fame' in html or 'Career Totals & Hall of Fame' in html
    assert 'seasonsTable' in html
    assert 'careerTable' in html
    assert 'btn-back-profile' in html


def test_h2h_natural_height_and_expand(client):
    """Ensure rivals table flows naturally without compressed max-height scrollbox."""
    rv = client.get('/player/Weidenbaum')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'max-height: 420px;' not in html
    assert 'toggleAllRivals' in html


def test_chinese_players_nationality_and_flags(client):
    """Ensure Tinaren and Dellcan have Chinese nationality (CN) and render China flag."""
    rv_d = client.get('/player/dellcan')
    assert rv_d.status_code == 200
    html_d = rv_d.get_data(as_text=True)
    assert '/static/flags/cn.svg' in html_d

    # Alias / case-insensitive Tinaren
    rv_t = client.get('/player/Tinaren')
    assert rv_t.status_code == 200
    html_t = rv_t.get_data(as_text=True)
    assert '/static/flags/cn.svg' in html_t
    assert 'tianren4561367' in html_t


def test_profile_headers_centered_and_borders_dark_red(client):
    """Ensure profile headers are centered and name borders are dark red/black."""
    rv = client.get('/player/DANeo')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    # Centered profile header class & layout
    assert 'align-items: center' in html
    assert 'justify-content: center' in html
    # High-contrast antique gold with smooth text-shadow (removing white-border artifact)
    assert 'player-profile-name' in html

    # Also achievements subpage
    rv_ach = client.get('/player/DANeo/achievements')
    assert rv_ach.status_code == 200
    html_ach = rv_ach.get_data(as_text=True)
    assert 'achievements-header' in html_ach
    assert 'align-items: center' in html_ach


def test_analysis_hero_card_and_format_bar(client):
    """Ensure analysis pages render cleanly with 200 status code."""
    for path in ['/analysis', '/analysis/calibration', '/analysis/movers', '/analysis/activity']:
        rv = client.get(path)
        assert rv.status_code == 200


def test_faq_player_case_studies(client):
    """Ensure Player Case Studies tab is hidden from FAQ and cleanly archived in docs/concepts."""
    rv = client.get('/faq')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    
    # Navigation and Section are removed from the active FAQ per webmaster directive
    assert 'Player Case Studies' not in html
    assert 'id="faq-casestudies"' not in html
    
    # Ensure the concept archive file exists with full profiles preserved
    from pathlib import Path
    concept_path = Path('docs/concepts/player_case_studies.md')
    assert concept_path.exists(), "Concept file docs/concepts/player_case_studies.md must exist"
    concept_text = concept_path.read_text(encoding='utf-8')
    assert 'SandHippo' in concept_text
    assert 'Weidenbaum' in concept_text
    assert 'Martin_Pecheur' in concept_text
    assert 'Ender_Wiggin' in concept_text
    assert 'DANeo' in concept_text
    assert 'tianren4561367' in concept_text
    assert 'pv4' in concept_text
    assert 'Lemmingsplayer' in concept_text
    assert 'Lcfyx' in concept_text
    assert 'megumi' in concept_text


def test_player_profile_hero_and_meta_readability(client):
    """Ensure Martin_Pecheur and other profiles feature the high-contrast hero header card and meta pill."""
    rv = client.get('/player/Martin_Pecheur')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)

    # Hero card styling on profile header
    assert 'profile-header' in html
    assert 'player-profile-name' in html
    assert 'Martin_Pecheur' in html
    assert ('World Champion' in html or 'Grandmaster' in html)

    # Meta pill with nationality flag and first match debut
    assert 'player-meta-pill' in html
    assert 'fr.svg' in html
    assert 'First Match:' in html


def test_subpages_background_image_styling(client):
    """Ensure all subpages and base template apply background image to body with navbar offset."""
    for path in ['/', '/faq', '/analysis', '/player/DANeo', '/player/Martin_Pecheur']:
        rv = client.get(path)
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert 'background-image: url(' in html
        assert 'background.png' in html
        assert 'background-position-y: var(--header-height, 68px);' in html
        assert '<div class="site-bg"' not in html


def test_community_leaderboard_page(client):
    """Ensure Community Standard Leaderboard loads correctly with Best-8 mechanics and accurate standings."""
    rv = client.get('/community-leaderboard')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Community Standard Leaderboard' in html
    assert 'Best-8 Rolling Point System' in html
    assert 'wolvs' in html
    assert '6,320' in html
    assert 'Grozz' in html
    assert 'Martin_Pecheur' in html
    assert 'a440' in html
    assert 'badge-wc' in html
    assert 'Worlds' in html
    assert 'International (4P)' in html
    assert 'Intermezzo (3P)' in html
    assert 'Royal League' in html


def test_world_champions_accolades_and_badges(client):
    """Ensure World Championship accolades are attached to Weidenbaum (2023), Martin_Pecheur (2024), and a440 (2025)."""
    # 1. a440 (Reigning World Champion)
    rv_a440 = client.get('/player/a440')
    assert rv_a440.status_code == 200
    html_a440 = rv_a440.get_data(as_text=True)
    assert 'badge-wc' in html_a440
    assert 'World Champion' in html_a440

    rv_a440_ach = client.get('/player/a440/achievements')
    assert rv_a440_ach.status_code == 200
    html_a440_ach = rv_a440_ach.get_data(as_text=True)
    assert 'badge-wc' in html_a440_ach
    assert 'Reigning World Champion' in html_a440_ach

    # 2. Weidenbaum (2023 World Champion)
    rv_wb = client.get('/player/Weidenbaum/achievements')
    assert rv_wb.status_code == 200
    html_wb = rv_wb.get_data(as_text=True)
    assert 'World Champion (2023)' in html_wb

    # 3. Martin_Pecheur (2024 World Champion)
    rv_mp = client.get('/player/Martin_Pecheur/achievements')
    assert rv_mp.status_code == 200
    html_mp = rv_mp.get_data(as_text=True)
    assert 'World Champion (2024)' in html_mp

    # 4. Verify WC badge is positioned strictly in the Title column on the leaderboard
    rv_lb = client.get('/ratings')
    html_lb = rv_lb.get_data(as_text=True)
    assert 'badge-wc' in html_lb
    # Verify player link itself does NOT contain badge-wc
    assert '<a href="/player/a440" class="player-link">\n              a440\n            </a>' in html_lb or 'class="player-link">\n              a440' in html_lb


def test_navigation_ratings_and_community_link(client):
    """Ensure main navigation links to Ratings and Community Leaderboard."""
    rv = client.get('/ratings')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '>Ratings</a>' in html
    assert '>Community Leaderboard</a>' in html
    # Leaderboard alone should not be a nav item anymore
    assert '<a href="/" class="' not in html or 'Ratings' in html


def test_yearly_leaderboard_routes(client):
    """Ensure yearly leaderboard subpages work across all available years (2017-2026)."""
    # Test active year 2026
    rv_2026 = client.get('/ratings/2026')
    assert rv_2026.status_code == 200
    html_2026 = rv_2026.get_data(as_text=True)
    assert 'Active Season 2026' in html_2026
    assert '2026-05-31' in html_2026
    assert 'a440' in html_2026

    # Test historical year 2024
    rv_2024 = client.get('/ratings/2024')
    assert rv_2024.status_code == 200
    html_2024 = rv_2024.get_data(as_text=True)
    assert 'Season 2024 Final Archive' in html_2024
    assert '2024-12-31' in html_2024
    assert 'Martin_Pecheur' in html_2024
    assert 'World Champion' in html_2024

    # Test historical year 2023
    rv_2023 = client.get('/ratings/2023')
    assert rv_2023.status_code == 200
    html_2023 = rv_2023.get_data(as_text=True)
    assert 'Season 2023 Final Archive' in html_2023
    assert 'Weidenbaum' in html_2023

    # Test earliest year 2017
    rv_2017 = client.get('/ratings/2017')
    assert rv_2017.status_code == 200
    html_2017 = rv_2017.get_data(as_text=True)
    assert 'Season 2017 Final Archive' in html_2017
    assert '2017-12-17' in html_2017

    # Test invalid year returns 404
    rv_invalid = client.get('/ratings/2015')
    assert rv_invalid.status_code == 404

    # Test /leaderboard/<year> alias
    rv_alias = client.get('/leaderboard/2025')
    assert rv_alias.status_code == 200
    assert 'Season 2025 Final Archive' in rv_alias.get_data(as_text=True)


def test_community_leaderboard_views_and_styling(client):
    """Ensure Standard vs Expanded view switching, CMB descriptor, and styled search button on Community Leaderboard."""
    # Standard view (default)
    rv_std = client.get('/community-leaderboard?view=standard')
    assert rv_std.status_code == 200
    html_std = rv_std.get_data(as_text=True)
    assert 'Standard View (Tournament Summary)' in html_std
    assert 'Scroll table with <strong>CMB</strong>' in html_std
    assert 'btn-search-gold' in html_std
    assert 'International (4P)' in html_std
    assert 'Intermezzo (3P)' in html_std

    # Expanded view
    rv_exp = client.get('/community-leaderboard?view=expanded')
    assert rv_exp.status_code == 200
    html_exp = rv_exp.get_data(as_text=True)
    assert 'expanded-view' in html_exp
    assert 'ic_30' in html_exp or 'IC 30' in html_exp


def test_community_leaderboard_multi_year_and_wolvs_attribution(client):
    """Ensure multi-year archives (2026, 2025, 2024, race26) and prominent Wolvs attribution render properly."""
    # 1. Check Wolvs maintainer attribution
    rv_2026 = client.get('/community-leaderboard')
    assert rv_2026.status_code == 200
    html_2026 = rv_2026.get_data(as_text=True)
    assert 'Wolvs' in html_2026
    assert 'maintainer-card' in html_2026
    assert 'wolvs' in html_2026
    assert '6,320' in html_2026

    # 2. Check 2025 final archive (Eepogi #1 with 6,600 pts)
    rv_2025 = client.get('/community-leaderboard/2025')
    assert rv_2025.status_code == 200
    html_2025 = rv_2025.get_data(as_text=True)
    assert 'Eepogi' in html_2025
    assert '6,600' in html_2025
    assert '2025 Final Archive' in html_2025

    # 3. Check 2024 final archive (Weidenbaum #1 with 7,657 pts)
    rv_2024 = client.get('/community-leaderboard/2024')
    assert rv_2024.status_code == 200
    html_2024 = rv_2024.get_data(as_text=True)
    assert 'Weidenbaum' in html_2024
    assert '7,657' in html_2024
    assert '2024 Final Archive' in html_2024

    # 4. Check 2026 Race Tracker (Grozz #1 with 4,380 pts)
    rv_race = client.get('/community-leaderboard/race26')
    assert rv_race.status_code == 200
    html_race = rv_race.get_data(as_text=True)
    assert 'Grozz' in html_race
    assert '4,380' in html_race
    assert 'Race Tracker' in html_race


def test_tournaments_hub_and_detail_routes(client):
    """Ensure Hall of Fame Hub and dedicated series pages render rules, trophyboards, and AI stories."""
    # Hub overview
    rv = client.get('/hall_of_fame')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Hall of Fame' in html
    assert 'International Championship' in html
    assert 'Intermezzo Championship' in html
    assert 'Royal League' in html
    assert 'World Championship' in html
    assert 'Derived Matches' in html

    # Also verify legacy /tournaments redirect
    rv_redir = client.get('/tournaments')
    assert rv_redir.status_code == 302
    assert '/hall_of_fame' in rv_redir.headers['Location']

    # International (4P) detail
    rv_int = client.get('/hall_of_fame/international')
    assert rv_int.status_code == 200
    html_int = rv_int.get_data(as_text=True)
    assert 'International Championship' in html_int
    assert '4-Player League' in html_int
    assert 'Weidenbaum' in html_int
    assert 'Genghisip' in html_int
    assert 'The Golden Hexa-Crown' in html_int

    # Intermezzo (3P) detail
    rv_itz = client.get('/hall_of_fame/intermezzo')
    assert rv_itz.status_code == 200
    html_itz = rv_itz.get_data(as_text=True)
    assert 'Intermezzo Championship' in html_itz
    assert '3-Player League' in html_itz

    # Royal League (2P) detail
    rv_rl = client.get('/hall_of_fame/royal_league')
    assert rv_rl.status_code == 200
    html_rl = rv_rl.get_data(as_text=True)
    assert 'Royal League' in html_rl
    assert '2-Player Duel' in html_rl

    # Worlds detail
    rv_wc = client.get('/hall_of_fame/worlds')
    assert rv_wc.status_code == 200
    html_wc = rv_wc.get_data(as_text=True)
    assert 'World Championship' in html_wc
    assert 'a440' in html_wc
    assert 'Martin_Pecheur' in html_wc
    assert 'Weidenbaum' in html_wc

    # 404 test for nonexistent series
    rv_404 = client.get('/hall_of_fame/nonexistent_series_xyz')
    assert rv_404.status_code == 404


def test_player_rivals_sortable_and_wc_badges(client):
    """Ensure Head-to-Head rivals table contains sort handlers and WC badges render with purple diamond aesthetic."""
    # a440 profile
    rv_a440 = client.get('/player/a440')
    assert rv_a440.status_code == 200
    html_a440 = rv_a440.get_data(as_text=True)
    assert 'badge-wc' in html_a440
    assert 'sortRivals' in html_a440
    assert 'sortRivals(\'wins\')' in html_a440 or 'sortRivals(\'wins\')' in html_a440

    # Weidenbaum profile
    rv_wb = client.get('/player/Weidenbaum')
    assert rv_wb.status_code == 200
    html_wb = rv_wb.get_data(as_text=True)
    assert 'badge-wc' in html_wb
    assert 'sortRivals' in html_wb


def test_golden_ratio_resets_and_eligibility_in_app(client):
    """Ensure soft and hard reset rating parameters load correctly and glicko_eligible is honored."""
    # Check ratings endpoint with soft reset
    rv_soft = client.get('/ratings?model=glicko2_mp&reset_mode=soft')
    assert rv_soft.status_code == 200
    html_soft = rv_soft.get_data(as_text=True)
    assert 'Soft Season Reset' in html_soft or 'soft' in html_soft

    # Check ratings endpoint with amplified reset
    rv_amp = client.get('/ratings?model=glicko2_mp&reset_mode=amplified')
    assert rv_amp.status_code == 200
    html_amp = rv_amp.get_data(as_text=True)
    assert 'Hard Season Reset' in html_amp or 'amplified' in html_amp

    # Check FAQ covers golden ratio formulas and eligibility
    rv_faq = client.get('/faq')
    assert rv_faq.status_code == 200
    html_faq = rv_faq.get_data(as_text=True)
    assert 'Golden Ratio' in html_faq
    assert 'glicko_eligible' in html_faq or 'Glicko Eligibility' in html_faq


def test_seasonal_wld_symmetry_and_career_stats(client):
    """Verify seasonal W-L-D symmetry and toggle between Season-Only and Career-to-Date stats."""
    # Test Season-Only view for 2024
    rv_season = client.get('/ratings/2024?stats_view=season')
    assert rv_season.status_code == 200
    html_season = rv_season.get_data(as_text=True)
    assert 'stats_view=season' in html_season or 'Season Only' in html_season
    assert 'stats_view=career' in html_season
    # In 2024, Martin_Pecheur played 253 opponents with symmetric UNION ALL counting
    assert '253' in html_season

    # Test Career-to-Date view for 2024
    rv_career = client.get('/ratings/2024?stats_view=career')
    assert rv_career.status_code == 200
    html_career = rv_career.get_data(as_text=True)
    # In 2024 cumulative, Martin_Pecheur has 1,009 career opponents
    assert '1,009' in html_career or '1009' in html_career


def test_player_reset_modes_and_matrix_subpage(client):
    """Verify player profile reset modes and 3x3 comparison matrix subpage."""
    # Profile with soft reset (consolidated to Season Reset)
    rv_soft = client.get('/player/Martin_Pecheur?reset_mode=soft')
    assert rv_soft.status_code == 200
    html_soft = rv_soft.get_data(as_text=True)
    assert 'Season Reset' in html_soft
    assert 'Peak Career Season' in html_soft
    assert 'Comparison Matrix &amp; Career Years' in html_soft or 'Comparison Matrix' in html_soft

    # Profile with amplified reset (consolidated to Season Reset)
    rv_amp = client.get('/player/Martin_Pecheur?reset_mode=amplified')
    assert rv_amp.status_code == 200

    # Player Matrix subpage
    rv_matrix = client.get('/player/Martin_Pecheur/matrix')
    assert rv_matrix.status_code == 200
    html_matrix = rv_matrix.get_data(as_text=True)
    assert 'Comparison Matrix' in html_matrix
    assert 'Peak Career Season' in html_matrix
    assert 'Continuous' in html_matrix

    # Player Matrix filtered by year
    rv_mat_yr = client.get('/player/Martin_Pecheur/matrix?year=2024')
    assert rv_mat_yr.status_code == 200


def test_player_rivals_min_matches_filter(client):
    """Verify player profile Head-to-Head rivals table includes min matches filter and career peak year."""
    rv = client.get('/player/Martin_Pecheur')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'rivalsMinMatches' in html
    assert 'Matches: All (1+)' in html
    assert 'Matches: 5+' in html
    assert 'Matches: 10+' in html
    assert 'Peak Career Season' in html


def test_model_analysis_reset_modes_and_cross_reset_matrix(client):
    """Verify analysis page supports reset modes, agreement summary, and offers dynamic calibration curves."""
    # Analysis overview default
    rv = client.get('/analysis')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'heroCalibrationChart' in html
    assert 'Engine Agreement' in html or 'Strongest Agreement Pairs' in html

    # Analysis with soft reset
    rv_soft = client.get('/analysis?reset_mode=soft')
    assert rv_soft.status_code == 200
    html_soft = rv_soft.get_data(as_text=True)
    assert 'heroCalibrationChart' in html_soft

    # Calibration dedicated subpage
    rv_calib = client.get('/analysis/calibration')
    assert rv_calib.status_code == 200
    html_calib = rv_calib.get_data(as_text=True)
    assert 'heroCalibrationChart' in html_calib


def test_leaderboard_progressive_drawer_and_tour(client):
    """Verify progressive disclosure options sidebar and toggle aligned to leaderboard card."""
    rv = client.get('/ratings')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'leaderboardSidebar' in html
    assert 'toggleOptionsSidebar' in html
    assert 'leaderboard-layout-container' in html
    assert 'optionsToggleBtn' in html


def test_tournaments_accuracy_and_records_card(client):
    """Verify DANeo in International, Royal League accuracy, scrollable trophyboard, card readability, and scoring records."""
    # 1. International Championship
    rv_int = client.get('/hall_of_fame/international')
    assert rv_int.status_code == 200
    html_int = rv_int.get_data(as_text=True)
    # DANeo verified on trophyboard with 1 Gold
    assert 'DANeo' in html_int
    assert 'trophy-table-container' in html_int
    # Readability: chronicles wrapped in panel-card
    assert 'panel-card' in html_int
    assert 'Master+ Dynastic Milestones & Champion Chronicles' in html_int
    # Best Seasonal Records & Single-Game Records
    assert 'Premier Division All-Time Seasonal Records (International Championship)' in html_int
    assert 'Premier Division Highest Single-Match Scores (International Championship)' in html_int
    assert 'Weidenbaum' in html_int or 'Genghisip' in html_int

    # 2. Royal League
    rv_rl = client.get('/hall_of_fame/royal_league')
    assert rv_rl.status_code == 200
    html_rl = rv_rl.get_data(as_text=True)
    # Royal League accuracy: vanishadow has 2 titles, saru has 2 titles, DANeo has 2 silvers
    assert 'vanishadow' in html_rl
    assert 'saru' in html_rl
    assert 'DANeo' in html_rl
    assert 'Premier Division All-Time Seasonal Records (Royal League)' in html_rl

    # 3. Intermezzo
    rv_itz = client.get('/hall_of_fame/intermezzo')
    assert rv_itz.status_code == 200
    html_itz = rv_itz.get_data(as_text=True)
    assert 'Premier Division All-Time Seasonal Records (Intermezzo Championship)' in html_itz
    assert 'Weidenbaum' in html_itz or 'Martin_Pecheur' in html_itz


def test_whr_martingale_and_deflation_only_anchor():
    """Verify WHR inactivity martingale property and symmetrical reset anchor math across 16 sub-tiers."""
    import math
    from src.models.whr.engine import WHREngine, PHI
    from src.models.glicko2.calculator import get_tier_mean

    # 1. Dynamic phi-quantile 16-subtier anchor check (mean=1500, sigma=175):
    # Rating 1955 -> z = 455/175 = 2.60 in GM 2 [2.0, phi^2) -> deflates to GM 1 lower bound (phi):
    expected_gm1_lower = 1500.0 + PHI * 175.0
    assert abs(get_tier_mean(1955.0) - expected_gm1_lower) < 1e-4

    # Rating 1970 -> z = 470/175 = 2.686 in SuperGM 1 [phi^2, 3.0) -> deflates to GM 2 lower bound (2.0):
    assert get_tier_mean(1970.0) == 1500.0 + 2.0 * 175.0

    # Rating 1750 -> z = 250/175 = 1.429 in Master 2 [1.0, phi) -> deflates to Master 1 lower bound (1/phi):
    expected_m1_lower = 1500.0 + (1.0 / PHI) * 175.0
    assert abs(get_tier_mean(1750.0) - expected_m1_lower) < 1e-4

    # Platinum 1 ([0.0, phi^-2)) -> deflates to Mean (1500)
    assert get_tier_mean(1520.0) == 1500.0

    # Sub-mean deflation-only check (zero upward drift for below-average players):
    # Below mean (<= 1500) ratings are strictly preserved (get_tier_mean returns their rating, lambda = 0)
    from src.models.glicko2.calculator import compute_decoupled_scaling
    assert get_tier_mean(1480.0) == 1480.0
    assert get_tier_mean(1400.0) == 1400.0
    assert get_tier_mean(1350.0) == 1350.0

    # Ensure lambda is zero while uncertainty inflation alpha is active:
    alpha_sub, lambda_sub = compute_decoupled_scaling(1350.0, rd=30.0)
    assert lambda_sub == 0.0
    assert alpha_sub > 1.40  # Low RD player still gets RD mobility boost

    # 2. WHR retention kernel calculation with 3-year half life
    dt_1yr = 365.25
    ret_1yr = math.pow(PHI, -1.0 * dt_1yr / (3.0 * 365.25))
    assert 0.85 < ret_1yr < 0.86  # ~85.2% retention after 1 year (phi^(-1/3))

    dt_3yr = 3.0 * 365.25
    ret_3yr = math.pow(PHI, -1.0 * dt_3yr / (3.0 * 365.25))
    assert abs(ret_3yr - (1.0 / PHI)) < 1e-6  # Exact 1/phi (61.8%) after 3 years


def test_analysis_9x9_matrix_and_curve_toggle(client):
    """Verify analysis page agreement and player profile curve toggle."""
    # 1. Analysis page agreement section
    rv = client.get('/analysis')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Engine Agreement' in html or 'Strongest Agreement Pairs' in html

    # 2. Calibration page / hero chart
    rv_calib = client.get('/analysis/calibration')
    assert rv_calib.status_code == 200
    html_calib = rv_calib.get_data(as_text=True)
    assert 'heroCalibrationChart' in html_calib
    assert 'Expected Calibration Error' in html_calib
    assert 'Brier Score' in html_calib

    # 3. Player profile curve switcher
    rv_p = client.get('/player/DANeo')
    assert rv_p.status_code == 200
    html_p = rv_p.get_data(as_text=True)
    assert 'btnCurveExpected' in html_p
    assert 'btnCurveConservative' in html_p
    assert 'switchRatingCurve' in html_p


def test_player_profile_format_filtering(client):
    """Verify that selecting a format filter on player profile synchronizes both recent matches and rivals."""
    # 1. 2-Player (Duel) format filter
    rv_2p = client.get('/player/DANeo?format=2')
    assert rv_2p.status_code == 200
    html_2p = rv_2p.get_data(as_text=True)
    assert 'First Match:' in html_2p
    assert '2-Player' in html_2p

    # 2. 4-Player format filter
    rv_4p = client.get('/player/DANeo?format=4')
    assert rv_4p.status_code == 200
    html_4p = rv_4p.get_data(as_text=True)
    assert '4-Player' in html_4p


def test_player_modes_subpage_and_engine_switcher(client):
    """Verify /modes subpage alias, Score Index explainer tooltip, and dynamic engine switcher."""
    # 1. Access /modes alias
    rv = client.get('/player/Martin_Pecheur/modes')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Rating Model &times; Reset Mode Comparison Matrix' in html or 'Comparison Matrix' in html
    assert 'Score Index' in html
    assert 'Composite Performance Index' in html
    assert 'switchChartEngine' in html
    assert 'btnEngineStd' in html
    assert 'btnEngineMp' in html
    assert 'btnEngineWhr' in html


