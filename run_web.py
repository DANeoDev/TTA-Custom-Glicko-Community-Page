import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web.app import create_app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f'Starting TTA Rating Portal at http://127.0.0.1:{port}')
    app = create_app()
    app.run(host='127.0.0.1', port=port, debug=False)
