import os
import sys
import tempfile
import traceback
from pathlib import Path

# 環境変数を最初に設定（Vercel環境であることを示す）
os.environ['VERCEL'] = '1'

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 現在のディレクトリをプロジェクトルートに設定
try:
    os.chdir(project_root)
except Exception as e:
    print(f"Warning: Could not change directory to {project_root}: {e}", file=sys.stderr)

# Vercel環境では/tmpディレクトリを使用（インポート前に設定）
UPLOAD_DIR = Path('/tmp/uploads')
try:
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
except Exception as e:
    print(f"Warning: Could not create upload directory: {e}", file=sys.stderr)

# 一時ファイル用のディレクトリも/tmpに設定
tempfile.tempdir = '/tmp'

# Flaskアプリをインポート
app = None
import_error = None

try:
    from web_html_editor import app
    
    # アップロードフォルダを設定（念のため再設定）
    app.config['UPLOAD_FOLDER'] = str(UPLOAD_DIR)
    
    # アップロードディレクトリを再作成（念のため）
    try:
        Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True, parents=True)
    except Exception:
        pass
    
except ImportError as e:
    # インポートエラーの詳細を取得
    import_error = e
    error_trace = traceback.format_exc()
    print(f"ImportError: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    print(f"Project root: {project_root}", file=sys.stderr)
    print(f"Current dir: {os.getcwd()}", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    
    # エラー用の最小限のFlaskアプリを作成
    from flask import Flask, jsonify
    error_app = Flask(__name__)
    
    @error_app.route('/', defaults={'path': ''})
    @error_app.route('/<path:path>')
    def error_handler(path):
        return jsonify({
            'error': 'Application initialization failed',
            'type': 'ImportError',
            'message': str(e),
            'python_path': sys.path,
            'project_root': project_root,
            'current_dir': os.getcwd(),
            'traceback': error_trace.split('\n')[-15:]  # 最後の15行
        }), 500
    
    app = error_app
    
except Exception as e:
    # その他のエラー
    import_error = e
    error_trace = traceback.format_exc()
    print(f"Error: {e}", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    
    # エラー用の最小限のFlaskアプリを作成
    from flask import Flask, jsonify
    error_app = Flask(__name__)
    
    @error_app.route('/', defaults={'path': ''})
    @error_app.route('/<path:path>')
    def error_handler(path):
        return jsonify({
            'error': 'Application initialization failed',
            'type': type(e).__name__,
            'message': str(e),
            'traceback': error_trace.split('\n')[-15:]  # 最後の15行
        }), 500
    
    app = error_app

# アプリが正常に読み込まれたか確認
if app is None:
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def error_handler(path):
        return jsonify({
            'error': 'Application is None',
            'message': 'Failed to initialize application'
        }), 500

# Vercel用にhandlerをエクスポート（必須）
# VercelのPythonランタイムがhandlerをクラスとして扱おうとしている問題を回避するため、
# handlerを関数として定義し、その中でFlaskアプリを呼び出す
# VercelのPythonランタイムは、handlerが関数またはWSGIアプリケーションであることを期待している
# しかし、内部実装がクラスを期待している可能性があるため、関数として定義する
def handler(environ, start_response):
    """
    Vercel用のWSGIハンドラー
    environ: WSGI環境変数
    start_response: WSGI start_response関数
    """
    # FlaskアプリはWSGIアプリケーションなので、直接呼び出す
    return app(environ, start_response)

