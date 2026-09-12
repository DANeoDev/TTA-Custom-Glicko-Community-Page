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
    assert b'Model Diagnostics' in response.data
    assert b'Cross-Model Agreement Matrix' in response.data
    assert b'Official Title Rating Benchmarks' in response.data

    # Ensure Top Movers is accessible on its dedicated subpage
    movers_resp = client.get('/analysis/movers')
    assert movers_resp.status_code == 200
    assert b'Top Rank Movers' in movers_resp.data
