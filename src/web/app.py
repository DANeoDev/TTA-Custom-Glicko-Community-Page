import os
import sys
from pathlib import Path
from flask import Flask, session

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web.routes.leaderboard import leaderboard_bp, VALID_MODELS, VALID_FORMATS
from src.web.routes.player import player_bp
from src.web.routes.analysis import analysis_bp
from src.web.routes.faq import faq_bp
from src.web.routes.community import bp as community_bp
from src.web.routes.admin import admin_bp
from src.web.routes.hall_of_fame import hall_of_fame_bp
from flask import redirect, url_for

from markupsafe import Markup

def country_flag_emoji(code):
    if not code or len(code) != 2:
        return Markup('<span style="opacity: 0.5;">🌐</span>')
    c_lower = code.lower()
    return Markup(
        f'<img src="/static/flags/{c_lower}.svg" alt="{code.upper()}" '
        f'class="flag-icon-img" title="Country: {code.upper()}" '
        f'onerror="this.onerror=null; this.src=\'/static/flags/un.svg\';">'
    )

def create_app():
    static_dir = Path(__file__).resolve().parent / 'static'
    template_dir = Path(__file__).resolve().parent / 'templates'

    app = Flask(
        __name__,
        static_folder=str(static_dir),
        template_folder=str(template_dir)
    )
    app.secret_key = os.environ.get('SECRET_KEY') or os.environ.get('TTA_SECRET_KEY', 'tta-glicko2-whr-secret-2026')

    @app.context_processor
    def inject_context():
        active_model = session.get('active_model')
        if not active_model or active_model not in VALID_MODELS:
            active_model = 'glicko2_daneo'
            session['active_model'] = 'glicko2_daneo'
        active_format = session.get('active_format', 0)
        from src.data.db import get_all_cms_blocks, get_custom_cards
        try:
            cms_blocks = get_all_cms_blocks()
        except Exception:
            cms_blocks = {}

        def get_cms(page_id, block_key, default_title=None, default_content=None):
            override = cms_blocks.get((page_id, block_key))
            if override:
                return {
                    'title': override.get('title') or default_title,
                    'content': Markup(override.get('content_html') or default_content or ''),
                    'markdown': override.get('content_markdown') or '',
                    'is_custom': True,
                    'is_deleted': bool(override.get('is_deleted', 0)),
                    'relative_to': override.get('relative_to'),
                    'placement': override.get('placement'),
                    'is_custom_card': bool(override.get('is_custom_card', 0))
                }
            return {
                'title': default_title,
                'content': Markup(default_content or '') if default_content else '',
                'markdown': '',
                'is_custom': False,
                'is_deleted': False,
                'relative_to': None,
                'placement': None,
                'is_custom_card': False
            }

        def get_page_custom_cards(page_id):
            try:
                return get_custom_cards(page_id)
            except Exception:
                return []

        TITLE_FULL_NAMES = {
            'WC': 'World Champion',
            'GM': 'Grandmaster',
            'M': 'Master',
            'P': 'Platinum',
            'G': 'Gold',
            'S': 'Silver',
            'B': 'Bronze',
            'W': 'Wood'
        }

        def get_title_name(code):
            if not code:
                return ''
            return TITLE_FULL_NAMES.get(str(code).upper(), str(code))

        return {
            'active_model': active_model,
            'active_model_name': VALID_MODELS.get(active_model, 'GlickoD'),
            'models': VALID_MODELS,
            'active_format': active_format,
            'active_format_name': VALID_FORMATS.get(active_format, 'All Formats'),
            'formats': VALID_FORMATS,
            'get_flag': country_flag_emoji,
            'get_title_name': get_title_name,
            'max': max,
            'min': min,
            'cms_blocks': cms_blocks,
            'get_cms': get_cms,
            'get_custom_cards': get_page_custom_cards
        }

    # Redirect /tournaments to /hall_of_fame for seamless backwards compatibility
    @app.route('/tournaments')
    def tournaments_redirect():
        return redirect(url_for('hall_of_fame.index'))

    @app.route('/tournaments/<series_slug>')
    def tournaments_series_redirect(series_slug):
        return redirect(url_for('hall_of_fame.series_detail', series_slug=series_slug))

    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(faq_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(hall_of_fame_bp)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='127.0.0.1', port=port, debug=True)
