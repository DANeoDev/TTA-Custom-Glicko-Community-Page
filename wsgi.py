"""Production WSGI entry point for Through the Ages (TTA-Glicko2-WHR).

Configured for deployment on PythonAnywhere, Gunicorn, uWSGI, or any WSGI server.
Exposes `application` as the WSGI callable.
"""
import os
import sys
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure database directory exists and database indexes/pragmas are initialized
from src.data.db import init_db, get_connection

try:
    init_db()
    with get_connection() as conn:
        conn.execute("PRAGMA busy_timeout = 60000;")
except Exception as e:
    print(f"[WSGI Init Warning] DB initialization notice: {e}")

from src.web.app import create_app

# The WSGI callable expected by PythonAnywhere and Gunicorn
application = create_app()

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000, debug=False)