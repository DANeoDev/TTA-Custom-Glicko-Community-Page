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
    # Active players with >= 30 matches: 1,357
    assert '1,357' in html

    # Without minimum matches filter: 1,507 active players
    rv_all_min = client.get('/leaderboard?min_opps=0')
    assert rv_all_min.status_code == 200
    assert '1,507' in rv_all_min.get_data(as_text=True)

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
    assert 'Spearman Rank Correlation' in html

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
    """Ensure the calibration subpage renders with Brier scores and reliability data."""
    rv = client.get('/analysis/calibration')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Model Calibration & Reliability Curves' in html
    assert 'Brier Score' in html
    assert 'deepCalibChart' in html

def test_analysis_movers_subpage(client):
    """Ensure the top movers subpage renders with climbers and fallers."""
    rv = client.get('/analysis/movers')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Top Rank Movers' in html
    assert 'Top Rank Climbers' in html
    assert 'Top Rank Fallers' in html

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
        assert ach_count >= 150, f"Expected >= 150 players in player_achievements, got {ach_count}"
        assert rec_count >= 1000, f"Expected >= 1000 tournament records, got {rec_count}"

        weid = conn.execute('SELECT * FROM player_achievements WHERE player_name = "Weidenbaum"').fetchone()
        assert weid is not None
        assert weid['total_titles'] >= 10
        assert 'International' in weid['summary_text']

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
    """Ensure the main analysis overview displays Title Rating Benchmarks instead of Top Movers."""
    rv = client.get('/analysis')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Official Title Rating Benchmarks' in html
    assert 'Explore Top Movers Subpage' in html
    assert 'Grandmaster (GM)' in html
    assert 'Master (M)' in html
    assert 'Platinum (P)' in html
    assert 'Gold (G)' in html


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
    idx_s34 = html.find('Season 34')
    idx_s1 = html.find('Season 1')
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
    # Very dark red / almost black border via vector text-stroke
    assert '-webkit-text-stroke' in html
    assert 'paint-order: stroke fill' in html

    # Also achievements subpage
    rv_ach = client.get('/player/DANeo/achievements')
    assert rv_ach.status_code == 200
    html_ach = rv_ach.get_data(as_text=True)
    assert 'achievements-header' in html_ach
    assert 'align-items: center' in html_ach


def test_analysis_hero_card_and_format_bar(client):
    """Ensure analysis pages feature the opaque high-contrast hero card and format pill buttons."""
    for path in ['/analysis', '/analysis/calibration', '/analysis/movers', '/analysis/activity']:
        rv = client.get(path)
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert 'analysis-hero-card' in html
        assert 'analysis-hero-title' in html
        assert 'analysis-hero-desc' in html
        if path != '/analysis/activity':
            assert 'format-bar' in html
            assert 'format-btn' in html


