"""Webmaster Admin Blueprint for TTA-Glicko2-WHR.

Provides single-login administration for:
- Auto-registering tournaments (pasting URLs and uploading result tables).
- Triggering polite CGE match scraping.
- Reviewing dry-run diffs with safety backup creation before committing.
- Running tournament consistency and sanity checks.
- Triggering rating pipeline recomputation.
"""
import os
import re
import threading
from functools import wraps
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from src.data.db import (
    get_connection, log_pipeline_update,
    get_cms_block, save_cms_block, revert_cms_block,
    get_all_cms_blocks, revert_all_cms_blocks,
    delete_cms_block, restore_cms_block, get_custom_cards
)
from src.data.template_editor import hardcode_card_to_template
from src.scrapers.sources import (
    scan_tournament_sources,
    register_tournament_source,
    get_tournament_source_details,
    update_tournament_source,
    delete_tournament_source,
    infer_tournament_folder_from_title
)
try:
    from src.scrapers.cge import CGEClient, clean_target_path
except ImportError:
    CGEClient = None
    def clean_target_path(x): return x
from src.data.merger import (
    preview_scraped_matches,
    commit_new_matches,
    get_ingested_seasons_for_tournament,
    get_ingested_seasons_from_all_matches,
    get_canonical_player_map,
    get_added_tournaments_summary,
    export_update_snapshot,
    list_update_snapshots,
    set_active_delta_snapshot,
    get_active_delta_config,
    delete_update_snapshot
)
from src.data.parse_tournaments import ingest_community_leaderboard
from src.data.consistency import check_tournament_consistency
from src.data.completeness import evaluate_season_completeness
from run_pipeline import run_all

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COMMUNITY_SHEET_URL = "https://docs.google.com/spreadsheets/d/125moezP_WQwGL9Bxx3ev11bPtyIU6JUpXnF-_uIBV50/edit?gid=1110531447#gid=1110531447"

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKUP_DIR = PROJECT_ROOT / "data" / "raw" / "backups"

# In-memory store for pending scrape preview to avoid large cookie payloads
PENDING_MATCHES_CACHE = {}


def get_admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "tta-admin")


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Please sign in with your Webmaster password to access this area.", "warning")
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        entered_pw = request.form.get('password', '').strip()
        expected_pw = get_admin_password()

        if entered_pw and entered_pw == expected_pw:
            session['is_admin'] = True
            flash("Welcome to the Webmaster Dashboard.", "success")
            next_url = request.args.get('next') or url_for('admin.dashboard')
            return redirect(next_url)
        else:
            error = "Invalid Webmaster password. Please try again."

    return render_template('admin/login.html', error=error)


@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash("You have been signed out of the Webmaster Dashboard.", "info")
    return redirect(url_for('leaderboard.index'))


@admin_bp.route('')
@admin_required
def dashboard():
    # 1. Database metrics
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*), MAX(date) FROM matches")
        row = cur.fetchone()
        matches_count = row[0] if row else 0
        latest_match_date = row[1] if row else "N/A"

        cur = conn.execute("SELECT COUNT(*) FROM pairwise_matches")
        pairwise_count = cur.fetchone()[0]

        cur = conn.execute("SELECT COUNT(*) FROM players")
        players_count = cur.fetchone()[0]
    finally:
        conn.close()

    # 2. CGE Credentials Status (Masked privacy check)
    cge_user = os.getenv("CGE_USERNAME")
    cge_cookie = os.getenv("CGE_SESSION_COOKIE")
    has_cge_auth = bool(cge_user or cge_cookie)
    auth_method = "Cookie" if cge_cookie else ("Credentials" if cge_user else "None (Public Only)")

    # 3. Tournaments summary
    tournaments = scan_tournament_sources()

    # 4. Recent backups
    backups = []
    if BACKUP_DIR.exists():
        for b in sorted(BACKUP_DIR.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            backups.append({
                "name": b.name,
                "size_mb": round(b.stat().st_size / (1024 * 1024), 2),
                "modified": b.stat().st_mtime,
            })

    # 5. Added / uningested tournaments summary
    added_tournaments_summary = get_added_tournaments_summary()

    # 6. Community Leaderboard Stats
    community_stats = {
        "sheet_url": DEFAULT_COMMUNITY_SHEET_URL,
        "total_players": 0,
        "rank1_player": "None",
        "rank1_points": 0.0,
        "last_updated": None
    }
    try:
        cur = conn.execute("""
            SELECT 
                COUNT(*) as total_players,
                (SELECT player_name FROM community_leaderboard_entries WHERE edition = '2026' ORDER BY rank LIMIT 1) as rank1_player,
                (SELECT points FROM community_leaderboard_entries WHERE edition = '2026' ORDER BY rank LIMIT 1) as rank1_points
            FROM community_leaderboard_entries 
            WHERE edition = '2026'
        """)
        cl_row = cur.fetchone()
        if cl_row and cl_row["total_players"]:
            community_stats["total_players"] = cl_row["total_players"]
            community_stats["rank1_player"] = cl_row["rank1_player"] or "None"
            community_stats["rank1_points"] = cl_row["rank1_points"] or 0.0

        cl_csv = PROJECT_ROOT / "data" / "tournaments" / "Community_Leaderboard" / "TTA_Leaderboard_Q2_2026.csv"
        if cl_csv.exists():
            community_stats["last_updated"] = datetime.fromtimestamp(cl_csv.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    conn_snap = get_connection()
    try:
        snapshots = list_update_snapshots(conn=conn_snap)
        active_delta_config = get_active_delta_config(conn=conn_snap)
    finally:
        conn_snap.close()

    return render_template(
        'admin/dashboard.html',
        matches_count=matches_count,
        pairwise_count=pairwise_count,
        players_count=players_count,
        latest_match_date=latest_match_date,
        has_cge_auth=has_cge_auth,
        auth_method=auth_method,
        tournaments=tournaments,
        backups=backups,
        added_tournaments_summary=added_tournaments_summary,
        community_stats=community_stats,
        snapshots=snapshots,
        active_delta_config=active_delta_config
    )


@admin_bp.route('/tournaments')
@admin_required
def list_tournaments():
    tournaments = scan_tournament_sources()
    return render_template('admin/tournaments.html', tournaments=tournaments)


@admin_bp.route('/tournaments/add', methods=['POST'])
@admin_required
def add_tournament():
    source_url = request.form.get('source_url', '').strip()
    tourney_name = request.form.get('tournament_name', '').strip()
    standings_url = request.form.get('standings_url', '').strip()

    # Check for file upload
    result_csv_text = None
    csv_file = request.files.get('result_csv_file')
    if csv_file and csv_file.filename:
        try:
            result_csv_text = csv_file.read().decode('utf-8', errors='ignore')
        except Exception:
            pass

    if not source_url:
        flash("Source URL cannot be empty.", "error")
        return redirect(url_for('admin.dashboard'))

    # If folder name not provided, attempt to infer from URL or title
    if not tourney_name:
        m_id = re.search(r'/detail/(\d+)', source_url)
        if m_id:
            tourney_name = f"CGE_Tournament_{m_id.group(1)}"
        else:
            tourney_name = "Tournament_Source"

    clean_name = infer_tournament_folder_from_title(tourney_name)

    res = register_tournament_source(
        tournament_name=clean_name,
        source_url=source_url,
        standings_url=standings_url if standings_url else None,
        result_csv_content=result_csv_text if result_csv_text else None
    )

    flash(f"Tournament registered successfully in '{res['folder']}'! ({res['source_file']})", "success")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/tournaments/edit/<folder>', methods=['GET', 'POST'])
@admin_required
def edit_tournament(folder: str):
    details = get_tournament_source_details(folder)
    if not details:
        flash(f"Tournament folder '{folder}' not found.", "error")
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        new_folder = request.form.get('folder_name', '').strip()
        sources_content = request.form.get('sources_content', '')
        standings_url = request.form.get('standings_url', '').strip()

        try:
            res = update_tournament_source(
                folder_name=folder,
                new_folder_name=new_folder if new_folder else None,
                sources_content=sources_content,
                standings_url=standings_url if standings_url else None
            )
            flash(f"Tournament '{res['folder']}' updated successfully!", "success")
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            flash(f"Error updating tournament: {str(e)}", "error")
            return redirect(url_for('admin.edit_tournament', folder=folder))

    return render_template('admin/tournament_edit.html', t=details)


@admin_bp.route('/tournaments/delete/<folder>', methods=['POST'])
@admin_required
def delete_tournament(folder: str):
    try:
        success = delete_tournament_source(folder)
        if success:
            flash(f"Tournament directory '{folder}' was successfully deleted.", "success")
        else:
            flash(f"Could not delete tournament '{folder}': directory not found.", "error")
    except Exception as e:
        flash(f"Failed to delete tournament '{folder}': {str(e)}", "error")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/scrape', methods=['POST'])
@admin_required
def trigger_scrape():
    target_input = (request.form.get('tournament_url') or request.form.get('tournament_id') or '').strip()
    tourney_folder = (request.form.get('tournament_folder') or '').strip()
    if not target_input:
        flash("Please provide a valid CGE Tournament ID, stage path (e.g. '5000/9'), or detail URL.", "error")
        return redirect(url_for('admin.dashboard'))

    target_path = clean_target_path(target_input)
    if not target_path:
        flash("Could not parse a valid CGE tournament ID from the input.", "error")
        return redirect(url_for('admin.dashboard'))

    crawl_all = request.form.get('crawl_all_groups') in ('1', 'true', 'True', True)
    cas_val = request.form.get('crawl_all_stages')
    crawl_all_stages = True if cas_val is None else (cas_val in ('1', 'true', 'True', True))
    force_refresh = request.form.get('force_refresh') in ('1', 'true', 'True', True)
    glicko_eligible = request.form.get('glicko_eligible') not in ('0', 'false', 'False')

    try:
        client = CGEClient()

        # Check if the user specified a specific sub-stage (e.g. 5000/9 or 1234/7)
        has_explicit_stage = '/' in target_path and any(part.isdigit() for part in target_path.split('/')[1:])

        # Smart skipping: detect already-ingested seasons from all_matches.csv
        skip_seasons = None
        if not force_refresh:
            from src.data.merger import get_ingested_seasons_from_all_matches
            lookup_name = tourney_folder or target_path
            skip_seasons = get_ingested_seasons_from_all_matches(lookup_name)

        if crawl_all_stages and not has_explicit_stage:
            # Multi-stage crawl: crawls all stages discovered for this tournament, skipping already ingested
            parsed = client.crawl_tournament_all_stages(
                target_path,
                crawl_all_groups=crawl_all,
                force_refresh=force_refresh,
                skip_seasons=skip_seasons
            )
        elif crawl_all:
            parsed = client.crawl_season_all_groups(target_path, force_refresh=force_refresh)
        else:
            html = client.fetch_tournament_html(target_path, force_refresh=force_refresh)
        if not parsed["games"]:
            stages = parsed.get("stages", [])
            # If user provided base tournament ID (e.g. 5000) and active season has no games:
            if stages and "/" not in target_path:
                t_title_lower = parsed.get("title", "").lower()
                ingested = get_ingested_seasons_for_tournament(parsed["title"])
                candidate_stage = None
                # Check descending stages (e.g. Season 25 before Season 26)
                for st in sorted(stages, key=lambda s: s["season_num"], reverse=True):
                    sn = st["season_num"]
                    comp_sn = sn
                    if "international" in t_title_lower and sn <= 30:
                        comp_sn = sn + 9
                    elif ("transcontinental" in t_title_lower or "tcl" in t_title_lower) and sn < 100:
                        comp_sn = sn + 54
                    if comp_sn not in ingested and sn != parsed.get("active_season_num"):
                        candidate_stage = st
                        break

                if not candidate_stage and len(stages) > 1:
                    for st in sorted(stages, key=lambda s: s["season_num"], reverse=True):
                        if st["season_num"] != parsed.get("active_season_num"):
                            candidate_stage = st
                            break

                if candidate_stage:
                    flash(
                        f"Notice: Season {parsed.get('active_season_num', '')} has 0 completed games. "
                        f"Automatically switched to latest completed season: {candidate_stage['name']} ({candidate_stage['path']}).",
                        "info"
                    )
                    target_path = candidate_stage["path"]
                    if crawl_all:
                        parsed = client.crawl_season_all_groups(target_path)
                    else:
                        html = client.fetch_tournament_html(target_path, force_refresh=True)
                        parsed = client.parse_tournament_html(html, target=target_path)

        if not parsed["games"]:
            flash(f"Scraped '{parsed['title']}' ({target_path}), but no completed games could be found in the current view.", "warning")
            return redirect(url_for('admin.dashboard'))

        # Preview against existing dataset
        diff = preview_scraped_matches(parsed["games"])

        # Check whether this season was already ingested
        active_season = parsed.get("active_season_num")
        t_title_lower = parsed.get("title", "").lower()
        effective_season = active_season
        if active_season and "international" in t_title_lower and active_season <= 30:
            effective_season = active_season + 9
        elif active_season and ("transcontinental" in t_title_lower or "tcl" in t_title_lower) and active_season < 100:
            effective_season = active_season + 54

        ingested_seasons = get_ingested_seasons_for_tournament(parsed["title"])
        season_status_msg = ""
        if effective_season and effective_season in ingested_seasons:
            season_status_msg = f"Season {effective_season} is already recorded in our historical database."

        # Cache in pending dictionary
        token = f"scrape_{target_path.replace('/', '_')}_{int(os.times().system * 100)}"
        PENDING_MATCHES_CACHE[token] = {
            "tournament_title": parsed["title"],
            "tournament_id": target_path,
            "new_matches": diff["new_matches"],
            "glicko_eligible": glicko_eligible,
        }

        # Evaluate season completeness
        completeness = evaluate_season_completeness(parsed["games"], parsed["title"], active_season)

        return render_template(
            'admin/diff_preview.html',
            token=token,
            title=f"{parsed['title']} (Stage: {parsed.get('active_season_num') or 'Main'})",
            total_scraped=diff["total_scraped"],
            duplicates_count=diff["duplicate_count"],
            new_matches_count=diff["new_matches_count"],
            new_matches=diff["new_matches"][:100],  # Preview top 100
            season_status_msg=season_status_msg,
            is_finished=parsed.get("is_finished", True),
            status_label=parsed.get("status_label", "Finished"),
            completeness=completeness,
        )

    except Exception as e:
        flash(f"Scraping failed for tournament '{target_path}': {str(e)}", "error")
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/scrape-all', methods=['POST'])
@admin_required
def scrape_all_tournaments():
    cas_val = request.form.get('crawl_all_stages')
    crawl_all_stages = True if cas_val is None else (cas_val in ('1', 'true', 'True', True))
    crawl_all = request.form.get('crawl_all_groups') in ('1', 'true', 'True', True)
    force_refresh = request.form.get('force_refresh') in ('1', 'true', 'True', True)
    glicko_eligible = request.form.get('glicko_eligible') not in ('0', 'false', 'False')

    try:
        from src.data.merger import get_ingested_seasons_from_all_matches
        tournaments = scan_tournament_sources()
        client = CGEClient()
        all_scraped_games = []
        scraped_tourney_names = []

        for t in tournaments:
            cge_ids = t.get("cge_ids", [])
            if not cge_ids:
                continue

            folder = t.get("folder", "")
            skip_seasons = None
            if not force_refresh:
                skip_seasons = get_ingested_seasons_from_all_matches(folder)

            for cid in cge_ids:
                cid_str = str(cid)
                if crawl_all_stages:
                    parsed = client.crawl_tournament_all_stages(
                        cid_str,
                        crawl_all_groups=crawl_all,
                        force_refresh=force_refresh,
                        skip_seasons=skip_seasons
                    )
                elif crawl_all:
                    parsed = client.crawl_season_all_groups(cid_str, force_refresh=force_refresh)
                else:
                    html = client.fetch_tournament_html(cid_str, force_refresh=force_refresh)
                    parsed = client.parse_tournament_html(html, target=cid_str)

                games = parsed.get("games", [])
                if games:
                    all_scraped_games.extend(games)
                    scraped_tourney_names.append(f"{folder or cid_str} ({len(games)} games)")

        if not all_scraped_games:
            flash("Scraped all tracked tournaments, but no completed games could be found in the current view.", "warning")
            return redirect(url_for('admin.dashboard'))

        # Preview against existing dataset
        diff = preview_scraped_matches(all_scraped_games)

        token = f"scrape_all_{int(os.times().system * 100)}"
        PENDING_MATCHES_CACHE[token] = {
            "tournament_title": "All Tracked Tournaments",
            "tournament_id": "all",
            "new_matches": diff["new_matches"],
            "glicko_eligible": glicko_eligible,
        }

        return render_template(
            'admin/diff_preview.html',
            token=token,
            title="All Tracked Tournaments",
            total_scraped=diff["total_scraped"],
            duplicates_count=diff["duplicate_count"],
            new_matches_count=diff["new_matches_count"],
            new_matches=diff["new_matches"][:100],
            season_status_msg=f"Scraped {len(scraped_tourney_names)} tournament(s): {', '.join(scraped_tourney_names)}",
            is_finished=True,
            status_label="Batch Complete",
            completeness=None,
        )

    except Exception as e:
        flash(f"Scraping all tournaments failed: {str(e)}", "error")
        return redirect(url_for('admin.dashboard'))



@admin_bp.route('/commit', methods=['POST'])
@admin_required
def commit_matches():
    token = request.form.get('token', '').strip()
    entry = PENDING_MATCHES_CACHE.get(token)

    if not entry or not entry.get("new_matches"):
        flash("No pending matches found to commit or preview session expired.", "warning")
        return redirect(url_for('admin.dashboard'))

    matches_to_add = entry["new_matches"]
    is_eligible = entry.get("glicko_eligible", True)
    res = commit_new_matches(matches_to_add, create_backup=True, glicko_eligible=is_eligible)

    # Log pipeline update for delta tracking
    try:
        conn = get_connection()
        prev_date_row = conn.execute("SELECT MAX(period_date) as max_date FROM rating_history").fetchone()
        prev_date = prev_date_row['max_date'] if prev_date_row else None
        log_pipeline_update(
            conn,
            cutoff_date=prev_date,
            matches_added=res['rows_appended'],
            description=f"Scraped {entry.get('tournament_title', 'Tournament')}"
        )
        conn.close()
    except Exception as e:
        print(f"[LOG UPDATE ERROR] {e}")

    # Remove from cache
    PENDING_MATCHES_CACHE.pop(token, None)

    season_files_msg = ""
    if res.get("season_files_updated"):
        s_files = [f"{sf['folder']}/{sf['file']} ({sf['rows_written']} rows)" for sf in res["season_files_updated"]]
        season_files_msg = f" Season files updated: {', '.join(s_files)}."

    flash(
        f"Success! {res['rows_appended']} matches appended to all_matches.csv and {res['pairwise_inserted']} pairwise records added to SQLite.{season_files_msg} Safety backup saved as '{res['backup_created']}'.",
        "success"
    )
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/consistency', methods=['GET', 'POST'])
@admin_required
def consistency():
    selected_tournament = request.args.get('tournament') or request.form.get('tournament') or 'Royal League'
    report = check_tournament_consistency(selected_tournament)
    all_tourneys = scan_tournament_sources()
    return render_template(
        'admin/consistency.html',
        report=report,
        selected_tournament=selected_tournament,
        all_tourneys=all_tourneys
    )


@admin_bp.route('/recompute', methods=['POST'], endpoint='recompute')
@admin_required
def recompute_ratings():
    # 1. Ensure all_matches.csv is assembled with all confirmed season CSVs
    try:
        from scripts.assemble_all_matches import assemble
        assemble(dry_run=False)
    except Exception as e:
        print(f"[ASSEMBLE WARNING] {e}")

    # 2. Export update snapshot (data/updates/{date}_tournaments.txt and {date}_all_games.csv)
    try:
        export_update_snapshot()
    except Exception as e:
        print(f"[SNAPSHOT WARNING] {e}")

    # 3. Get the list of newly added tournaments / stages
    added_summary = get_added_tournaments_summary()

    # Asynchronously run the ratings pipeline so HTTP connection doesn't time out
    def worker():
        try:
            run_all(skip_ingestion=False)
        except Exception as e:
            print(f"[RECOMPUTE ERROR] {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    if added_summary:
        summary_items_html = "".join([f"<li style='margin-bottom: 0.25rem;'>{item}</li>" for item in added_summary])
        msg = (
            f"<div><strong>Rating calculation pipeline launched in background!</strong> (Recalculating Glicko-2 & WHR across all formats)</div>"
            f"<div style='margin-top: 0.6rem; font-size: 0.92rem; color: #cfd8dc;'>The following tournaments & stages are included in this run:</div>"
            f"<ul style='margin: 0.5rem 0 0 1.2rem; padding: 0; font-family: monospace; font-size: 0.88rem; color: #fff8e1;'>"
            f"{summary_items_html}"
            f"</ul>"
        )
    else:
        msg = "Rating calculation pipeline launched in background! (Recalculating Glicko-2 & WHR across all formats)."

    flash(msg, "info")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/community-leaderboard/sync', methods=['POST'])
@admin_required
def sync_community_leaderboard():
    sheet_url = (request.form.get('sheet_url') or DEFAULT_COMMUNITY_SHEET_URL).strip()
    try:
        # Extract spreadsheet ID and gid
        m_id = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
        m_gid = re.search(r'[#&?]gid=(\d+)', sheet_url)
        if not m_id:
            flash("Invalid Google Sheets URL format. Expected 'https://docs.google.com/spreadsheets/d/...'", "error")
            return redirect(url_for('admin.dashboard'))

        sheet_id = m_id.group(1)
        gid = m_gid.group(1) if m_gid else '1110531447'
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

        import requests
        resp = requests.get(csv_export_url, timeout=25)
        if resp.status_code != 200:
            flash(f"Failed to fetch Google Sheet: HTTP {resp.status_code}", "error")
            return redirect(url_for('admin.dashboard'))

        csv_text = resp.text
        if len(csv_text.strip().splitlines()) < 10:
            flash("Downloaded Google Sheet data is too small or invalid.", "error")
            return redirect(url_for('admin.dashboard'))

        cl_dir = PROJECT_ROOT / "data" / "tournaments" / "Community_Leaderboard"
        cl_dir.mkdir(parents=True, exist_ok=True)
        target_file = cl_dir / "TTA_Leaderboard_Q2_2026.csv"

        # Backup if exists
        if target_file.exists():
            backup_name = f"TTA_Leaderboard_Q2_2026_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            (cl_dir / backup_name).write_text(target_file.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")

        target_file.write_text(csv_text, encoding="utf-8")

        # Ingest into SQLite database
        conn = get_connection()
        canonical_map = get_canonical_player_map(conn)
        ingest_community_leaderboard(conn, canonical_map)

        cur = conn.execute("SELECT COUNT(*), (SELECT player_name FROM community_leaderboard_entries WHERE edition = '2026' ORDER BY rank LIMIT 1) FROM community_leaderboard_entries WHERE edition = '2026'")
        row = cur.fetchone()
        count_2026 = row[0] if row else 0
        top_player = row[1] if row else "Unknown"
        conn.close()

        flash(
            f"Successfully synchronized Community Leaderboard from Google Sheet! "
            f"<strong>{count_2026:,} players</strong> ingested for 2026 (Rolling Q2) &bull; Reigning #1: <strong>{top_player}</strong>. "
            f"<a href='{url_for('community.index')}' style='color: #ffd700; text-decoration: underline; margin-left: 0.5rem;'>View Live Leaderboard &rarr;</a>",
            "success"
        )
    except Exception as e:
        flash(f"Error synchronizing Community Leaderboard: {str(e)}", "error")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/snapshots/select', methods=['POST'])
@admin_required
def select_delta_snapshot():
    snapshot_filenames = request.form.getlist('snapshot_filenames')
    if not snapshot_filenames:
        single = request.form.get('snapshot_filename', '').strip()
        if single:
            snapshot_filenames = [single]

    if not snapshot_filenames:
        flash("No snapshot files selected.", "warning")
        return redirect(url_for('admin.dashboard'))

    res = set_active_delta_snapshot(snapshot_filenames)
    joined_names = ", ".join(snapshot_filenames)
    flash(
        f"Rating Update Delta Period baseline successfully updated to <strong>{joined_names}</strong> "
        f"(Earliest Cutoff Date: <strong>{res.get('cutoff_date', 'N/A')}</strong> &bull; Max Delta Span). "
        f"Leaderboard deltas will now calculate relative to this timeframe.",
        "success"
    )
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/snapshots/delete', methods=['POST'])
@admin_required
def delete_snapshot():
    snapshot_filename = request.form.get('snapshot_filename', '').strip()
    if not snapshot_filename:
        flash("No snapshot file specified for deletion.", "warning")
        return redirect(url_for('admin.dashboard'))

    success = delete_update_snapshot(snapshot_filename)
    if success:
        flash(f"Deleted snapshot file <strong>{snapshot_filename}</strong>.", "info")
    else:
        flash(f"Could not find or delete snapshot file {snapshot_filename}.", "error")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/snapshots/refresh', methods=['POST'])
@admin_required
def refresh_snapshots():
    conn = get_connection()
    try:
        snapshots = list_update_snapshots(conn=conn)
        flash(f"Refreshed update snapshots list: {len(snapshots)} snapshots found in chronological order.", "info")
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))


# =========================================================================
# In-Place Universal CMS Content Endpoints
# =========================================================================

@admin_bp.route('/cms/get_block', methods=['GET'])
@admin_required
def get_cms_block_route():
    page_id = request.args.get('page_id', '').strip()
    block_key = request.args.get('block_key', '').strip()
    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key required'}), 400

    block = get_cms_block(page_id, block_key)
    if block:
        return jsonify({'status': 'success', 'block': block})
    return jsonify({'status': 'not_found', 'message': 'Block not customized yet'}), 200


@admin_bp.route('/cms/save_block', methods=['POST'])
@admin_required
def save_cms_block_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip()
    block_key = (data.get('block_key') or '').strip()
    title = (data.get('title') or '').strip()
    content_markdown = (data.get('content_markdown') or '').strip()
    content_html = (data.get('content_html') or '').strip()
    relative_to = (data.get('relative_to') or '').strip() or None
    placement = (data.get('placement') or '').strip() or None
    sort_order = int(data.get('sort_order', 0))
    is_custom_card = 1 if data.get('is_custom_card') else 0
    is_deleted = 1 if data.get('is_deleted') else 0

    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key cannot be empty'}), 400

    if not content_html:
        content_html = content_markdown

    save_cms_block(
        page_id=page_id,
        block_key=block_key,
        title=title,
        content_html=content_html,
        content_markdown=content_markdown,
        relative_to=relative_to,
        placement=placement,
        sort_order=sort_order,
        is_custom_card=is_custom_card,
        is_deleted=is_deleted
    )
    return jsonify({
        'status': 'success',
        'message': f'Block {page_id}:{block_key} saved successfully.',
        'block': {
            'page_id': page_id,
            'block_key': block_key,
            'title': title,
            'content_html': content_html,
            'content_markdown': content_markdown,
            'relative_to': relative_to,
            'placement': placement,
            'sort_order': sort_order,
            'is_custom_card': is_custom_card,
            'is_deleted': is_deleted
        }
    })


@admin_bp.route('/cms/delete_block', methods=['POST'])
@admin_required
def delete_cms_block_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip()
    block_key = (data.get('block_key') or '').strip()
    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key required'}), 400

    deleted = delete_cms_block(page_id, block_key)
    return jsonify({
        'status': 'success',
        'deleted': deleted,
        'message': f'Block {page_id}:{block_key} marked as deleted.'
    })


@admin_bp.route('/cms/restore_block', methods=['POST'])
@admin_required
def restore_cms_block_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip()
    block_key = (data.get('block_key') or '').strip()
    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key required'}), 400

    restored = restore_cms_block(page_id, block_key)
    return jsonify({
        'status': 'success',
        'restored': restored,
        'message': f'Block {page_id}:{block_key} successfully restored.'
    })


@admin_bp.route('/cms/hardcode_block', methods=['POST'])
@admin_required
def hardcode_cms_block_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip()
    block_key = (data.get('block_key') or '').strip()
    title = (data.get('title') or '').strip()
    content_html = (data.get('content_html') or '').strip()
    content_markdown = (data.get('content_markdown') or '').strip()
    relative_to = (data.get('relative_to') or '').strip() or None
    placement = (data.get('placement') or '').strip() or None
    is_custom_card = bool(data.get('is_custom_card'))

    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key required'}), 400

    if not content_html:
        content_html = content_markdown

    try:
        res = hardcode_card_to_template(
            page_id=page_id,
            block_key=block_key,
            title=title,
            content_html=content_html,
            content_markdown=content_markdown,
            relative_to=relative_to,
            placement=placement,
            is_custom_card=is_custom_card
        )
        return jsonify({
            'status': 'success',
            'message': f"Block {page_id}:{block_key} hardcoded directly into {res['file']}!",
            'file': res['file']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/cms/revert_block', methods=['POST'])
@admin_required
def revert_cms_block_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip()
    block_key = (data.get('block_key') or '').strip()
    if not page_id or not block_key:
        return jsonify({'status': 'error', 'message': 'page_id and block_key required'}), 400

    deleted = revert_cms_block(page_id, block_key)
    return jsonify({
        'status': 'success',
        'reverted': deleted,
        'message': f'Block {page_id}:{block_key} reverted to default.'
    })


@admin_bp.route('/cms/list', methods=['GET'])
@admin_required
def list_cms_blocks_route():
    all_blocks = get_all_cms_blocks()
    block_list = list(all_blocks.values())
    return jsonify({
        'status': 'success',
        'count': len(block_list),
        'blocks': block_list
    })


@admin_bp.route('/cms/custom_cards', methods=['GET'])
def get_custom_cards_route():
    page_id = request.args.get('page_id')
    cards = get_custom_cards(page_id=page_id)
    return jsonify({
        'status': 'success',
        'count': len(cards),
        'cards': cards
    })


@admin_bp.route('/cms/revert_all', methods=['POST'])
@admin_required
def revert_all_cms_blocks_route():
    data = request.get_json(silent=True) or request.form
    page_id = (data.get('page_id') or '').strip() or None
    deleted_count = revert_all_cms_blocks(page_id=page_id)
    return jsonify({
        'status': 'success',
        'reverted_count': deleted_count,
        'message': f'Successfully reverted {deleted_count} block(s) to default.'
    })



