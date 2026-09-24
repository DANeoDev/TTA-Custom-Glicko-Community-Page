"""FAQ Route with dynamic statistics and webmaster editable sections."""
from flask import Blueprint, render_template, request, session, jsonify
import numpy as np
from src.data.db import get_connection
from src.web.routes.analysis import compute_calibration

faq_bp = Blueprint('faq', __name__)


@faq_bp.route('/faq')
def index():
    conn = get_connection()
    try:
        cur = conn.execute("""
            SELECT rating
            FROM player_ratings
            WHERE model_type = 'glicko2_mp' AND player_count = 0 AND opponents_count >= 15
        """)
        rows = cur.fetchall()
        if rows:
            ratings = [r['rating'] for r in rows]
            dynamic_mean = round(float(np.mean(ratings)), 1)
            active_player_count = len(ratings)
        else:
            dynamic_mean = 1500.0
            active_player_count = 0

        # Load custom/edited sections
        sec_rows = conn.execute("SELECT key, title, content, updated_at FROM faq_sections").fetchall()
        custom_sections = {r['key']: dict(r) for r in sec_rows}

        # Dynamic Calibration Data for Glicko-2 Standard vs MP-Weighted comparison
        # (Synchronized directly with the /analysis benchmark metrics)
        calib_wf_all = compute_calibration(conn, player_count=0, eval_mode='walk_forward')
        calib_wf_3p = compute_calibration(conn, player_count=3, eval_mode='walk_forward')
        calib_wf_4p = compute_calibration(conn, player_count=4, eval_mode='walk_forward')

        calib_models = calib_wf_all.get('models', {})
        calib_summary = {
            'matches_evaluated': calib_models.get('glicko2_mp', {}).get('matches', 308863),
            'glicko2_mp': calib_models.get('glicko2_mp', {'brier': 0.2141, 'ece_pct': 1.15}),
            'glicko2_std': calib_models.get('glicko2_std', {'brier': 0.2143, 'ece_pct': 1.47}),
            'glicko2_mp_soft': calib_models.get('glicko2_mp_soft', {'brier': 0.2147, 'ece_pct': 0.93}),
            'glicko2_std_soft': calib_models.get('glicko2_std_soft', {'brier': 0.2150, 'ece_pct': 1.05}),
            'glicko2_mp_3p': calib_wf_3p.get('models', {}).get('glicko2_mp', {'brier': 0.2178, 'ece_pct': 1.43}),
            'glicko2_std_3p': calib_wf_3p.get('models', {}).get('glicko2_std', {'brier': 0.2186, 'ece_pct': 2.05}),
            'glicko2_mp_4p': calib_wf_4p.get('models', {}).get('glicko2_mp', {'brier': 0.2224, 'ece_pct': 1.96}),
            'glicko2_std_4p': calib_wf_4p.get('models', {}).get('glicko2_std', {'brier': 0.2240, 'ece_pct': 3.24}),
        }

        return render_template(
            'faq.html',
            dynamic_mean=dynamic_mean,
            active_player_count=active_player_count,
            custom_sections=custom_sections,
            calib_summary=calib_summary
        )
    finally:
        conn.close()


@faq_bp.route('/faq/save_section', methods=['POST'])
def save_section():
    """Allows authenticated webmaster to update FAQ section content."""
    if not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Admin authentication required.'}), 403

    key = request.form.get('key', '').strip()
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()

    if not key or not content:
        return jsonify({'status': 'error', 'message': 'Section key and content cannot be empty.'}), 400

    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO faq_sections (key, title, content, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, title, content))
        return jsonify({'status': 'success', 'message': 'Section updated successfully.'})
    finally:
        conn.close()