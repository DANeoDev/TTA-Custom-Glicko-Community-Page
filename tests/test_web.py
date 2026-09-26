import pytest
from src.web.app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_leaderboard_route_200(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Through the Ages' in response.data
    assert b'Competitive Leaderboard' in response.data

def test_model_switching(client):
    # Switch to MP-Weighted
    r_mp = client.get('/?model=glicko2_mp')
    assert r_mp.status_code == 200
    assert b'Glicko-2 MP-Weighted' in r_mp.data

    # Switch to WHR
    r_whr = client.get('/?model=whr')
    assert r_whr.status_code == 200
    assert b'Whole-History Rating' in r_whr.data

def test_leaderboard_search(client):
    # Search for DireNTropy
    response = client.get('/?search=DireNTropy')
    assert response.status_code == 200
    assert b'DireNTropy' in response.data

def test_player_profile_route(client):
    response = client.get('/player/DireNTropy')
    assert response.status_code == 200
    assert b'DireNTropy' in response.data
    assert b'Historical Rating Trajectory' in response.data
    assert b'Recent Matches' in response.data
    assert b'Head-to-Head' in response.data

def test_unknown_player_404(client):
    response = client.get('/player/NonExistentPlayerXYZ123')
    assert response.status_code == 404

def test_analysis_route_200(client):
    response = client.get('/analysis')
    assert response.status_code == 200
    assert b'Model Diagnostics' in response.data or b'Calibration' in response.data
    assert b'Webmaster Assessment' in response.data or b'Agreement' in response.data

    # Ensure Multi-Engine Comparison is accessible on /analysis/movers
    movers_resp = client.get('/analysis/movers')
    assert movers_resp.status_code == 200
    assert b'Multi-Engine Player Comparison' in movers_resp.data


def test_player_matrix_with_glicko2_daneo(client):
    with client.session_transaction() as sess:
        sess['active_model'] = 'glicko2_daneo'
    resp = client.get('/player/a440/matrix')
    assert resp.status_code == 200
    assert b'GlickoD' in resp.data
    assert b'Peak Career Season' in resp.data


def test_player_profile_match_deltas(client):
    resp = client.get('/player/a440?model=glicko2_daneo')
    assert resp.status_code == 200
    assert b'Game History' in resp.data
    assert b'&Delta;R' in resp.data or b'Delta;R' in resp.data or b'Replay' in resp.data


def test_player_suggest_api(client):
    # Short queries return empty list
    r_empty = client.get('/api/players/suggest?q=')
    assert r_empty.status_code == 200
    assert r_empty.get_json() == {'suggestions': []}

    r_one = client.get('/api/players/suggest?q=d')
    assert r_one.status_code == 200
    assert r_one.get_json() == {'suggestions': []}

    # Query 'dan'
    r_dan = client.get('/api/players/suggest?q=dan')
    assert r_dan.status_code == 200
    names = [s['name'] for s in r_dan.get_json()['suggestions']]
    assert 'DANeo' in names

    # Query 'arthur' -> verifies ArthursDad with corrected Bronze badge 'B'
    r_arthur = client.get('/api/players/suggest?q=arthur')
    assert r_arthur.status_code == 200
    arthur_entry = next((s for s in r_arthur.get_json()['suggestions'] if s['name'] == 'ArthursDad'), None)
    assert arthur_entry is not None
    assert arthur_entry['title'] == 'B'

