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
    app.secret_key = os.environ.get('TTA_SECRET_KEY', 'tta-glicko2-whr-secret-2026')

    @app.context_processor
    def inject_context():
        active_model = session.get('active_model', 'glicko2_std')
        active_format = session.get('active_format', 0)
        return {
            'active_model': active_model,
            'active_model_name': VALID_MODELS.get(active_model, 'Glicko-2 Standard'),
            'models': VALID_MODELS,
            'active_format': active_format,
            'active_format_name': VALID_FORMATS.get(active_format, 'All Formats'),
            'formats': VALID_FORMATS,
            'get_flag': country_flag_emoji
        }

    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(faq_bp)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='127.0.0.1', port=port, debug=True)
