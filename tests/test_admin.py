"""Tests for Webmaster admin authentication and routes."""
import pytest
from src.web.app import create_app
from src.web.routes.admin import get_admin_password

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_admin_requires_login(client):
    # Unauthenticated GET /admin should redirect to /admin/login
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin/login' in resp.headers['Location']

def test_admin_login_flow(client):
    admin_pwd = get_admin_password()

    # GET login page
    resp = client.get('/admin/login')
    assert resp.status_code == 200
    assert b'Webmaster Access' in resp.data

    # POST incorrect password
    resp = client.post('/admin/login', data={'password': 'wrong_password_12345'}, follow_redirects=True)
    assert b'Invalid Webmaster password' in resp.data

    # POST correct password
    resp = client.post('/admin/login', data={'password': admin_pwd}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Webmaster Operations & Pipeline Control' in resp.data

    # Verify subsequent access to dashboard without redirect
    resp_dash = client.get('/admin')
    assert resp_dash.status_code == 200
    assert b'Tracked Tournament Directories' in resp_dash.data

    # Logout
    resp_logout = client.get('/admin/logout', follow_redirects=True)
    assert resp_logout.status_code == 200
    # Next access to /admin redirects again
    resp_recheck = client.get('/admin', follow_redirects=False)
    assert resp_recheck.status_code == 302

def test_admin_consistency_and_add_tournament(client):
    # Log in first
    client.post('/admin/login', data={'password': get_admin_password()}, follow_redirects=True)

    # Access consistency page
    resp_cons = client.get('/admin/consistency?tournament=Royal+League')
    assert resp_cons.status_code == 200
    assert b'Tournament Consistency &amp; Sanity Checker' in resp_cons.data or b'Tournament Consistency & Sanity Checker' in resp_cons.data

    # Add tournament through admin route
    resp_add = client.post('/admin/tournaments/add', data={
        'source_url': 'https://account.czechgames.com/tournaments/detail/8888',
        'tournament_name': 'Test_Admin_Cup'
    }, follow_redirects=True)
    assert resp_add.status_code == 200
    assert b'Tournament registered successfully' in resp_add.data

    # Cleanup test tournament folder
    import shutil
    from pathlib import Path
    test_dir = Path(__file__).resolve().parents[1] / "data" / "tournaments" / "Test_Admin_Cup"
    if test_dir.exists():
        shutil.rmtree(test_dir)

def test_admin_commit_flow(client):
    client.post('/admin/login', data={'password': get_admin_password()}, follow_redirects=True)
    from src.web.routes.admin import PENDING_MATCHES_CACHE
    token = "test_token_123"
    PENDING_MATCHES_CACHE[token] = {
        "tournament_title": "Test Tournament",
        "tournament_id": "9999",
        "new_matches": [],
        "glicko_eligible": True,
    }
    resp = client.post('/admin/commit', data={'token': token}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"No pending matches found" in resp.data


def test_admin_add_tournament_with_standings_url(client):
    client.post('/admin/login', data={'password': get_admin_password()}, follow_redirects=True)

    resp_add = client.post('/admin/tournaments/add', data={
        'source_url': 'https://account.czechgames.com/tournaments/detail/9999',
        'tournament_name': 'Test_Standings_Cup',
        'standings_url': 'https://docs.google.com/spreadsheets/d/test-sheet-id/edit#gid=0'
    }, follow_redirects=True)
    assert resp_add.status_code == 200
    assert b'Tournament registered successfully' in resp_add.data

    import shutil
    from pathlib import Path
    test_dir = Path(__file__).resolve().parents[1] / "data" / "tournaments" / "Test_Standings_Cup"
    assert test_dir.exists()
    sources_files = list(test_dir.glob("*_sources.md"))
    assert len(sources_files) == 1
    content = sources_files[0].read_text(encoding="utf-8")
    assert "https://docs.google.com/spreadsheets/d/test-sheet-id/edit#gid=0" in content

    # Cleanup
    shutil.rmtree(test_dir)


def test_admin_scrape_all(client, monkeypatch):
    client.post('/admin/login', data={'password': get_admin_password()}, follow_redirects=True)

    from unittest.mock import MagicMock
    import src.web.routes.admin as admin_module

    # Mock CGEClient to return dummy matches quickly without hitting network
    mock_client = MagicMock()
    mock_client.crawl_tournament_all_stages.return_value = {
        "title": "Mock Cup",
        "games": [
            {
                "tournament": "Mock Cup",
                "date": "2026-03-01",
                "participants": [("Alice", 100.0), ("Bob", 80.0)]
            }
        ]
    }
    monkeypatch.setattr(admin_module, "CGEClient", lambda: mock_client)

    resp = client.post('/admin/scrape-all', data={
        'crawl_all_stages': '1',
        'crawl_all_groups': '1',
        'force_refresh': '0',
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'All Tracked Tournaments' in resp.data or b'Verified New Matches' in resp.data


def test_admin_edit_and_delete_tournament(client):
    client.post('/admin/login', data={'password': get_admin_password()}, follow_redirects=True)

    # 1. Create a tournament to edit
    resp_add = client.post('/admin/tournaments/add', data={
        'source_url': 'https://account.czechgames.com/tournaments/detail/7777',
        'tournament_name': 'Edit_Test_Cup'
    }, follow_redirects=True)
    assert resp_add.status_code == 200

    # 2. Access edit page (GET)
    resp_get = client.get('/admin/tournaments/edit/Edit_Test_Cup')
    assert resp_get.status_code == 200
    assert b'Edit Tournament: Edit_Test_Cup' in resp_get.data

    # 3. Post edit (update name and standings URL)
    resp_post = client.post('/admin/tournaments/edit/Edit_Test_Cup', data={
        'folder_name': 'Renamed_Test_Cup',
        'standings_url': 'https://docs.google.com/spreadsheets/d/renamed-id/edit#gid=0',
        'sources_content': 'https://account.czechgames.com/tournaments/detail/7777\nhttps://docs.google.com/spreadsheets/d/renamed-id/edit#gid=0'
    }, follow_redirects=True)
    assert resp_post.status_code == 200
    assert b"Tournament 'Renamed_Test_Cup' updated successfully" in resp_post.data

    # Verify old directory is gone and new directory exists
    from pathlib import Path
    base_dir = Path(__file__).resolve().parents[1] / "data" / "tournaments"
    assert not (base_dir / "Edit_Test_Cup").exists()
    assert (base_dir / "Renamed_Test_Cup").exists()

    # 4. Delete tournament (POST)
    resp_del = client.post('/admin/tournaments/delete/Renamed_Test_Cup', follow_redirects=True)
    assert resp_del.status_code == 200
    assert b"successfully deleted" in resp_del.data
    assert not (base_dir / "Renamed_Test_Cup").exists()
