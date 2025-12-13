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
# VercelのPythonランタイムが期待する形式に合わせる
# Flaskアプリを直接エクスポートするのではなく、関数としてラップする
def handler(request):
    """
    Vercel用のリクエストハンドラー
    request: Vercelのリクエストオブジェクト
    """
    # FlaskアプリをWSGIアプリケーションとして呼び出す
    # VercelのリクエストをWSGI環境に変換する必要がある
    # ただし、VercelのPythonランタイムは自動的にWSGIアプリケーションを処理できるはず
    # 直接appを返すのではなく、appを呼び出す関数として定義
    return app(request.environ, request.start_response) if hasattr(request, 'environ') else app

