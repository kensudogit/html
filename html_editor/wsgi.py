"""
WSGI config for html_editor project.
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'html_editor.settings')

from django.core.wsgi import get_wsgi_application

# WSGIアプリケーションを取得
application = get_wsgi_application()

# デバッグ用ログ
import logging
logger = logging.getLogger(__name__)
logger.info(f"WSGI application loaded. BASE_DIR: {BASE_DIR}")
print(f"WSGI application loaded. BASE_DIR: {BASE_DIR}", flush=True)
