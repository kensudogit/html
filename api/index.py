"""
Vercel用のDjango WSGIエントリポイント
このファイルは、Vercel(Serverless)上でDjangoアプリを起動するためのエントリポイントです。
"""
import os
import sys
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

# Vercel環境では/tmpディレクトリを使用（メディアファイル用）
MEDIA_ROOT = Path('/tmp/media')
try:
    MEDIA_ROOT.mkdir(exist_ok=True, parents=True)
except Exception as e:
    print(f"Warning: Could not create media directory: {e}", file=sys.stderr)

# Django設定を環境変数で上書き（Vercel環境用）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'html_editor.settings')
os.environ.setdefault('MEDIA_ROOT', str(MEDIA_ROOT))

# Django WSGIアプリケーションをインポート
application = None
import_error = None

try:
    # デバッグ情報を出力
    print(f"=== Django WSGI Loading ===", file=sys.stderr)
    print(f"Project root: {project_root}", file=sys.stderr)
    print(f"Current dir: {os.getcwd()}", file=sys.stderr)
    print(f"Python path (first 5): {sys.path[:5]}", file=sys.stderr)
    print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}", file=sys.stderr)
    
    # Django WSGIアプリケーションをインポート
    from html_editor.wsgi import application
    
    if application is None:
        raise ImportError("Django WSGI application is None")
    
    print("Django WSGI application loaded successfully", file=sys.stderr)
    
except ImportError as e:
    # インポートエラーの詳細を取得
    import_error = e
    error_trace = traceback.format_exc()
    print(f"ImportError: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    print(f"Project root: {project_root}", file=sys.stderr)
    print(f"Current dir: {os.getcwd()}", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    
    # エラー用の最小限のWSGIアプリケーションを作成
    def error_application(environ, start_response):
        error_response = {
            'error': 'Application initialization failed',
            'type': 'ImportError',
            'message': str(e),
            'python_path': sys.path,
            'project_root': project_root,
            'current_dir': os.getcwd(),
            'traceback': error_trace.split('\n')[-15:]  # 最後の15行
        }
        import json
        response_body = json.dumps(error_response, indent=2).encode('utf-8')
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [response_body]
    
    application = error_application
    
except Exception as e:
    # その他のエラー
    import_error = e
    error_trace = traceback.format_exc()
    print(f"Error: {e}", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    
    # エラー用の最小限のWSGIアプリケーションを作成
    def error_application(environ, start_response):
        error_response = {
            'error': 'Application initialization failed',
            'type': type(e).__name__,
            'message': str(e),
            'traceback': error_trace.split('\n')[-15:]  # 最後の15行
        }
        import json
        response_body = json.dumps(error_response, indent=2).encode('utf-8')
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [response_body]
    
    application = error_application

# アプリが正常に読み込まれたか確認
if application is None:
    def error_application(environ, start_response):
        error_response = {
            'error': 'Application is None',
            'message': 'Failed to initialize Django application'
        }
        import json
        response_body = json.dumps(error_response, indent=2).encode('utf-8')
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [response_body]
    
    application = error_application

# Vercel用にhandlerをエクスポート（必須）
# VercelのPythonランタイムは、handlerがWSGIアプリケーションであることを期待している
def handler(environ, start_response):
    """
    Vercel用のWSGIハンドラー
    environ: WSGI環境変数
    start_response: WSGI start_response関数
    """
    try:
        return application(environ, start_response)
    except Exception as e:
        # 実行時エラーをキャッチして詳細なエラーメッセージを返す
        error_trace = traceback.format_exc()
        print(f"Handler error: {e}", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        
        error_response = {
            'error': 'Handler execution failed',
            'type': type(e).__name__,
            'message': str(e),
            'path': environ.get('PATH_INFO', 'N/A'),
            'method': environ.get('REQUEST_METHOD', 'N/A'),
            'traceback': error_trace.split('\n')[-20:]  # 最後の20行
        }
        import json
        response_body = json.dumps(error_response, indent=2).encode('utf-8')
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [response_body]

