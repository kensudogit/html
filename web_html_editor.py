#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebベースHTMLエディタ
ブラウザ上でHTMLファイルを編集できるWebアプリケーション
"""

# このファイルは、FlaskでHTML編集UIを提供するメインアプリです。
# 主要機能: アップロード/保存/検索/構文チェック/プレビュー表示（iframe+Blob URL）

import os
import sys
import argparse
import shutil
import tempfile
import traceback
import base64
import json
import zipfile
import sqlite3
import yaml
import io
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for, send_file, session, render_template
from html_editor import HTMLEditor
from bs4 import BeautifulSoup
import secrets

# テンプレートディレクトリと静的ファイルディレクトリを設定
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'templates'  # CSSファイルもtemplatesディレクトリに配置

app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR), static_url_path='/static')

# リクエストログ（Railway環境でのデバッグ用）
@app.before_request
def log_request_info():
    """すべてのリクエストをログに記録"""
    try:
        msg = f"=== リクエスト受信 ===\nMethod: {request.method}\nPath: {request.path}\nURL: {request.url}\nRemote Address: {request.remote_addr}\nUser Agent: {request.headers.get('User-Agent', 'N/A')}"
        app.logger.info(msg)
        print(msg, flush=True)  # printも追加して確実にログを出力
    except Exception as e:
        app.logger.error(f"リクエストログ記録エラー: {e}")
        print(f"リクエストログ記録エラー: {e}", flush=True)

# CORS設定（Railway環境でのAPIリクエストを許可）
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    app.logger.info(f"=== レスポンス送信 ===")
    app.logger.info(f"Status: {response.status_code}")
    app.logger.info(f"Path: {request.path}")
    return response

# セッション管理の設定
# SECRET_KEYはセッションの暗号化に使用される
# 環境変数で指定されていない場合は、ランダムな32バイトの16進数文字列を生成
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Vercel環境では/tmpディレクトリを使用
if os.environ.get('VERCEL'):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'

# デフォルトHTMLディレクトリ（アップロードフォルダを使用）
app.config['DEFAULT_HTML_DIRECTORY'] = None

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB制限

# セッション別のファイル管理用ディクショナリ
# キー: セッションID（文字列）
# 値: ファイル情報の辞書 {'html_editor': HTMLEditorオブジェクト, 'html_file_path': ファイルパス}
# これにより、複数のユーザー（セッション）が同時に異なるHTMLファイルを編集できる
session_files = {}

# アップロードフォルダを作成
UPLOAD_DIR = Path(app.config['UPLOAD_FOLDER'])
try:
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
except Exception as e:
    # Vercel環境などでディレクトリ作成に失敗した場合は警告のみ
    if os.environ.get('VERCEL'):
        pass  # Vercel環境では/tmpは既に存在する
    else:
        print(f"Warning: Could not create upload directory: {e}", file=sys.stderr)

# フロントエンドのビルドディレクトリ
# Railway環境でのパス解決を改善（複数のパスを試す）
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'
# 代替パス（Railway環境でのパス解決の問題に対応）
_ALTERNATIVE_PATHS = [
    BASE_DIR / 'frontend' / 'dist',
    Path('frontend') / 'dist',
    Path('/app') / 'frontend' / 'dist',
    Path('/app') / 'dist',
    Path(os.getcwd()) / 'frontend' / 'dist',
    Path(os.getcwd()) / 'dist',
    Path('/usr/src/app') / 'frontend' / 'dist',
    Path('/usr/src/app') / 'dist',
]

# 大学データ管理用のデータベースパス
DB_PATH = UPLOAD_DIR / 'university_data.db'
UNIVERSITY_CONFIG_DIR = UPLOAD_DIR / 'university_configs'
UNIVERSITY_CONFIG_DIR.mkdir(exist_ok=True, parents=True)

# データベースの初期化
def init_database():
    """大学データ管理用のデータベースを初期化"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 大学マスタテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ページタイトルマスタテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_titles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 大学ごとのページデータテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS university_page_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            page_title_id INTEGER NOT NULL,
            content TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (page_title_id) REFERENCES page_titles(id),
            UNIQUE(university_id, page_title_id)
        )
    ''')
    
    # デフォルトのページタイトルを挿入
    default_titles = [
        '入学手続TOP',
        '個人情報取り扱いに関する同意条項宣誓書',
        '本人情報',
        '健康状況',
        '保護者情報',
        '身元保証人情報',
        '緊急連絡先情報',
        '入学前セミナー受講調査',
        '写真アップロード',
        '書類アップロード',
        'アンケート',
        '学費負担者情報',
        '外国語の履修に関する調査',
        '父母等の連絡',
        '誓約書',
        'アドミッション・ポリシー',
        '家族情報',
        '通学住所情報',
        '利用規約・個人情報取扱いに関する同意条項',
        '言語選択申請'
    ]
    
    for i, title in enumerate(default_titles):
        cursor.execute('''
            INSERT OR IGNORE INTO page_titles (title, display_order) 
            VALUES (?, ?)
        ''', (title, i))
    
    conn.commit()
    conn.close()

# アプリケーション起動時にデータベースを初期化
init_database()

# HTMLエディタのテンプレート（外部ファイルから読み込み）
# HTMLエディタのテンプレート（外部ファイルから読み込み）
def _load_editor_template():
    """エディタテンプレートをファイルから読み込む"""
    template_path = TEMPLATES_DIR / 'editor_template.html'
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        app.logger.error(f"エディタテンプレート読み込みエラー: {e}")
        return None

EDITOR_TEMPLATE = _load_editor_template()
if EDITOR_TEMPLATE is None:
    # フォールバック: 最小限のHTMLテンプレート
    EDITOR_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>HTMLエディタ{% if filename %} - {{ filename }}{% endif %}</title>
</head>
<body>
    <h1>テンプレート読み込みエラー</h1>
    <p>editor_template.htmlが見つかりません。</p>
</body>
</html>"""

                    showStatus('レポートの生成に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('レポートのエクスポート中にエラーが発生しました', 'error');
                console.error('Error exporting comparison report:', error);
            }
        };
        
    </script>
</body>
</html>
"""


def get_session_file_info():
    """
    セッションからファイル情報を取得
    
    Returns:
        dict: セッションに対応するファイル情報
            - 'html_editor': HTMLEditorオブジェクト（未選択時はNone）
            - 'html_file_path': ファイルパス（未選択時はNone）
    """
    # セッションIDを取得（存在しない場合は新規生成）
    session_id = session.get('session_id')
    if not session_id:
        # 新規セッションの場合、16バイトのランダムな16進数文字列を生成
        session_id = secrets.token_hex(16)
        session['session_id'] = session_id
        # セッション用のファイル情報を初期化
        session_files[session_id] = {
            'html_editor': None,
            'html_file_path': None
        }
    # セッションIDに対応するファイル情報を返す（存在しない場合は空の辞書を返す）
    return session_files.get(session_id, {
        'html_editor': None,
        'html_file_path': None
    })


def set_session_file_info(html_editor_obj, file_path):
    """
    セッションにファイル情報を保存
    
    Args:
        html_editor_obj: HTMLEditorオブジェクト
        file_path: ファイルパス（Pathオブジェクトまたは文字列）
    """
    # セッションIDを取得（存在しない場合は新規生成）
    session_id = session.get('session_id')
    if not session_id:
        # 新規セッションの場合、16バイトのランダムな16進数文字列を生成
        session_id = secrets.token_hex(16)
        session['session_id'] = session_id
    
    # セッションIDがsession_filesに存在しない場合は初期化
    if session_id not in session_files:
        session_files[session_id] = {}
    
    # セッションに対応するファイル情報を保存
    session_files[session_id]['html_editor'] = html_editor_obj
    session_files[session_id]['html_file_path'] = file_path


def _find_assets_dir():
    """assetsディレクトリを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    assets_dir = FRONTEND_DIST_DIR / 'assets'
    if assets_dir.exists() and assets_dir.is_dir():
        app.logger.info(f"assetsディレクトリを見つけました（FRONTEND_DIST_DIR）: {assets_dir}")
        return assets_dir
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        assets_dir = dist_dir / 'assets'
        if assets_dir.exists() and assets_dir.is_dir():
            app.logger.info(f"assetsディレクトリを見つけました（代替パス）: {assets_dir}")
            return assets_dir
    
    # 見つからない場合はログを出力
    app.logger.error(f"assetsディレクトリが見つかりません。試したパス:")
    app.logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'assets'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        app.logger.error(f"  - {dist_dir / 'assets'}")
    return None


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """静的アセット（JS、CSSなど）を配信"""
    try:
        # 複数のパスからassetsディレクトリを検索
        assets_dir = _find_assets_dir()
        if assets_dir:
            return send_from_directory(str(assets_dir), filename)
        else:
            # デフォルトのパスを試す
            app.logger.warning(f"assetsディレクトリが見つかりません。デフォルトパスを試します: {FRONTEND_DIST_DIR / 'assets'}")
            return send_from_directory(str(FRONTEND_DIST_DIR / 'assets'), filename)
    except Exception as e:
        app.logger.error(f"静的アセット配信エラー: {e}, filename: {filename}")
        # 404エラーを返す代わりに、空のレスポンスを返す（ブラウザのエラーを減らすため）
        return '', 404


@app.route('/favicon.ico')
def favicon():
    """faviconを返す（404エラーを防ぐため）"""
    try:
        # 複数のパスからfaviconを検索
        for dist_dir in _ALTERNATIVE_PATHS:
            favicon_path = dist_dir / 'favicon.ico'
            if favicon_path.exists():
                return send_file(str(favicon_path))
        
        # 見つからない場合は空のICOファイルを返す
        return send_file(io.BytesIO(b''), mimetype='image/x-icon')
    except Exception:
        return send_file(io.BytesIO(b''), mimetype='image/x-icon')


def _load_template(template_name, **kwargs):
    """テンプレートファイルを読み込んで変数を置換"""
    try:
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            app.logger.error(f"テンプレートファイルが見つかりません: {template_path}")
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 変数を置換
        for key, value in kwargs.items():
            content = content.replace(f'{{{key}}}', str(value))
        
        return content
    except Exception as e:
        app.logger.error(f"テンプレート読み込みエラー ({template_name}): {e}")
        return None


def _find_index_html():
    """index.htmlを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    index_path = FRONTEND_DIST_DIR / 'index.html'
    if index_path.exists():
        app.logger.info(f"index.htmlを見つけました（FRONTEND_DIST_DIR）: {index_path}")
        return index_path
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        index_path = dist_dir / 'index.html'
        if index_path.exists():
            app.logger.info(f"index.htmlを見つけました（代替パス）: {index_path}")
            return index_path
    
    # 見つからない場合はログを出力
    app.logger.error(f"index.htmlが見つかりません。試したパス:")
    app.logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'index.html'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        app.logger.error(f"  - {dist_dir / 'index.html'}")
    return None


def _serve_index_html():
    """index.htmlを返す共通関数"""
    try:
        # 詳細なログを出力（Railway環境でのデバッグ用）
        msg = f"=== index.html配信開始 ===\n現在の作業ディレクトリ: {os.getcwd()}\nスクリプトのディレクトリ: {Path(__file__).parent}\nFRONTEND_DIST_DIR: {FRONTEND_DIST_DIR}\nFRONTEND_DIST_DIR 存在確認: {FRONTEND_DIST_DIR.exists()}"
        app.logger.info(msg)
        print(msg, flush=True)  # printも追加して確実にログを出力
        
        # 複数のパスからindex.htmlを検索
        index_path = _find_index_html()
        
        if index_path:
            msg = f"index.htmlを配信します: {index_path}"
            app.logger.info(msg)
            print(msg, flush=True)
            return send_file(str(index_path))
        else:
            # ビルドファイルが存在しない場合は、エラーメッセージを返す
            app.logger.error(f"Reactビルドファイルが見つかりません。試したパス: {[str(p / 'index.html') for p in _ALTERNATIVE_PATHS]}")
            tried_paths_html = ''.join([f'<li>{str(p / "index.html")}</li>' for p in _ALTERNATIVE_PATHS])
            error_html = _load_template(
                'build_not_found.html',
                work_dir=os.getcwd(),
                script_dir=Path(__file__).parent,
                tried_paths=tried_paths_html
            )
            if error_html:
                return error_html, 500
            else:
                # フォールバック: テンプレートが読み込めない場合はインラインHTMLを返す
                return f"""
                <!DOCTYPE html>
                <html lang="ja">
                <head>
                    <meta charset="UTF-8">
                    <title>ビルドファイルが見つかりません</title>
                    <style>
                        body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                        .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                        .error h1 {{ color: #e53e3e; margin-top: 0; }}
                        .error p {{ margin: 10px 0; color: #4a5568; }}
                        .error ul {{ margin: 10px 0; padding-left: 20px; }}
                        .error li {{ margin: 5px 0; color: #4a5568; }}
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h1>ビルドファイルが見つかりません</h1>
                        <p>frontend/dist/index.html が存在しません。ビルドを実行してください。</p>
                        <p><strong>作業ディレクトリ:</strong> {os.getcwd()}</p>
                        <p><strong>スクリプトのディレクトリ:</strong> {Path(__file__).parent}</p>
                        <p><strong>試したパス:</strong></p>
                        <ul>{tried_paths_html}</ul>
                    </div>
                </body>
                </html>
                """, 500
    except Exception as e:
        error_details = traceback.format_exc()
        app.logger.error(f"index.html配信エラー: {error_details}")
        error_html = _load_template(
            'error_page.html',
            error_message=str(e),
            error_details=error_details
        )
        if error_html:
            return error_html, 500
        else:
            # フォールバック: テンプレートが読み込めない場合はインラインHTMLを返す
            return f"""
            <!DOCTYPE html>
            <html lang="ja">
            <head>
                <meta charset="UTF-8">
                <title>エラー</title>
                <style>
                    body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                    .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .error h1 {{ color: #e53e3e; margin-top: 0; }}
                    .error h2 {{ color: #2d3748; margin-top: 20px; }}
                    .error p {{ margin: 10px 0; color: #4a5568; }}
                    .error pre {{ background: #f0f0f0; padding: 15px; border-radius: 4px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>エラーが発生しました</h1>
                    <p><strong>エラーメッセージ:</strong> {str(e)}</p>
                    <h2>詳細:</h2>
                    <pre>{error_details}</pre>
                </div>
            </body>
            </html>
            """, 500


@app.route('/')
def index():
    """メインページ - Reactアプリケーションを配信"""
    msg = "=== ルートパス (/) へのリクエスト ==="
    app.logger.info(msg)
    print(msg, flush=True)  # printも追加して確実にログを出力
    try:
        result = _serve_index_html()
        msg = f"index() の戻り値の型: {type(result)}"
        app.logger.info(msg)
        print(msg, flush=True)
        return result
    except Exception as e:
        error_msg = f"index() でエラーが発生: {e}"
        app.logger.error(error_msg)
        print(error_msg, flush=True)
        import traceback
        tb = traceback.format_exc()
        app.logger.error(tb)
        print(tb, flush=True)
        raise


@app.errorhandler(404)
def handle_404(e):
    """404エラーハンドラー - APIルート以外はindex.htmlを返す（SPAルーティング）"""
    path = request.path
    msg = f"=== 404エラー発生 ===\nPath: {path}\nMethod: {request.method}\nURL: {request.url}\nError: {e}"
    app.logger.warning(msg)
    print(msg, flush=True)  # printも追加して確実にログを出力
    
    # 静的アセットの場合は404を返す（既にserve_assetsで処理されているが、念のため）
    if path.startswith('/assets/'):
        app.logger.warning(f"静的アセットが見つかりません: {path}")
        return '', 404
    
    # APIルートの場合は404を返す
    if path.startswith('/api/') or path.startswith('/save') or path.startswith('/upload') or \
       path.startswith('/files') or path.startswith('/search') or path.startswith('/structure') or \
       path.startswith('/validate') or path.startswith('/download') or path.startswith('/content') or \
       path.startswith('/reload') or path.startswith('/load/') or path.startswith('/delete/') or \
       path.startswith('/diff-analysis') or path.startswith('/gcd-template') or \
       path.startswith('/generate-university-pages') or path.startswith('/download-university-pages') or \
       path.startswith('/template-merge'):
        return jsonify({'error': 'Not found'}), 404
    
    # それ以外はReactアプリを返す（SPAルーティング）
    msg = f"404エラーをキャッチ: {path} -> index.htmlを返します"
    app.logger.info(msg)
    print(msg, flush=True)  # printも追加して確実にログを出力
    return _serve_index_html()


@app.route('/save', methods=['POST'])
def save():
    """ファイルを保存"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのみを保存
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        data = request.json
        content = data.get('content', '')
        
        # ファイルに保存
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(html_editor, html_file_path)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/content')
def content():
    """HTMLコンテンツを取得"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのコンテンツのみを返す
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None or not Path(html_file_path).exists():
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reload')
def reload():
    """ファイルを再読み込み"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのみを再読み込み
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(html_editor, html_file_path)
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/structure')
def structure():
    """構造情報を取得"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルの構造情報のみを返す
        file_info = get_session_file_info()
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return jsonify({'success': False, 'error': 'HTMLエディタが初期化されていません'}), 500
        
        info = html_editor.get_structure_info()
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/search', methods=['POST'])
def search():
    """要素を検索"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイル内でのみ検索を実行
        file_info = get_session_file_info()
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return jsonify({'success': False, 'error': 'HTMLエディタが初期化されていません'}), 500
        
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': '検索文字列が空です'})
        
        results = []
        
        # IDで検索
        element = html_editor.find_by_id(query)
        if element:
            results.append({
                'tag': element.name,
                'id': element.get('id', ''),
                'class': ' '.join(element.get('class', [])),
                'type': 'id',
                'text': element.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # クラスで検索
        elements = html_editor.find_by_class(query)
        for elem in elements[:10]:  # 最初の10個のみ
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'class',
                'text': elem.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # タグで検索
        elements = html_editor.find_by_tag(query)
        for elem in elements[:10]:  # 最初の10個のみ
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'tag',
                'text': elem.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # テキスト内容で検索（部分一致）
        try:
            text_elements = html_editor.find_by_text(query, exact=False)
            for text_node in text_elements[:10]:  # 最初の10個のみ
                # テキストノードの親要素を取得
                parent = text_node.parent if hasattr(text_node, 'parent') else None
                if parent:
                    results.append({
                        'tag': parent.name,
                        'id': parent.get('id', ''),
                        'class': ' '.join(parent.get('class', [])),
                        'type': 'text',
                        'text': text_node.strip()[:50] if isinstance(text_node, str) else str(text_node)[:50]
                    })
        except Exception as e:
            # テキスト検索でエラーが発生した場合は無視
            pass
        
        # HTMLソースコード全体で検索（エディタの内容を検索）
        # クライアント側から送られてくるHTMLソースを検索するため、
        # この検索はクライアント側で行う方が効率的
        # サーバー側では、BeautifulSoupで解析されたHTMLのみを検索
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルをアップロード"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        # ファイル名を安全にする
        filename = secure_filename(file.filename)
        
        # HTMLファイルかチェック
        if not (filename.lower().endswith('.html') or filename.lower().endswith('.htm')):
            return jsonify({'success': False, 'error': 'HTMLファイルのみアップロード可能です'}), 400
        
        # アップロードフォルダに保存
        file_path = UPLOAD_DIR / filename
        file.save(str(file_path))
        
        # セッションにファイル情報を保存
        # このセッションでアップロードしたファイルを選択状態にする
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(html_editor, file_path)
        
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/files')
def list_files():
    """アップロードされたファイル一覧を取得"""
    try:
        files = []
        for file_path in UPLOAD_DIR.glob('*.html'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size
            })
        for file_path in UPLOAD_DIR.glob('*.htm'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size
            })
        
        # ファイル名でソート
        files.sort(key=lambda x: x['name'])
        
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/load/<filename>')
def load_file(filename):
    """ファイルを読み込む"""
    try:
        # ファイル名を安全にする
        safe_filename = secure_filename(filename)
        file_path = UPLOAD_DIR / safe_filename
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # ファイルを読み込む
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # セッションにファイル情報を保存
        # このセッションで読み込んだファイルを選択状態にする
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(html_editor, file_path)
        
        return jsonify({'success': True, 'content': content, 'filename': safe_filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """ファイルを削除"""
    try:
        # ファイル名を安全にする
        safe_filename = secure_filename(filename)
        file_path = UPLOAD_DIR / safe_filename
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # 現在開いているファイルを削除する場合は、そのセッションのエディタをクリア
        # 削除対象のファイルを開いているすべてのセッションをチェック
        # 複数のセッションが同じファイルを開いている可能性があるため、すべてのセッションを確認
        for session_id, file_info in list(session_files.items()):
            session_file_path = file_info.get('html_file_path')
            if session_file_path and Path(session_file_path) == file_path:
                # 該当セッションのファイル情報をクリア
                session_files[session_id]['html_editor'] = None
                session_files[session_id]['html_file_path'] = None
        
        # ファイルを削除
        file_path.unlink()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/validate', methods=['POST'])
def validate():
    """HTMLの構文を検証"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'リクエストデータがありません'}), 400
        
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'error': 'コンテンツが空です'}), 400
        
        # 一時ファイルに保存して検証
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # HTMLEditorで検証
            temp_editor = HTMLEditor(temp_path)
            errors = temp_editor.validate_html()
            
            return jsonify({'success': True, 'errors': errors})
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_path)
            except:
                pass
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/diff-analysis', methods=['POST', 'OPTIONS'])
def diff_analysis():
    """27校の大学ホームページの差分を検出"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        options = data.get('options', {})
        
        # 空欄またはアップロードフォルダ指定の場合はアップロードフォルダを使用
        use_upload_dir = False
        if not directory or directory == '__upload__':
            # アップロードフォルダを使用
            directory = str(UPLOAD_DIR)
            use_upload_dir = True
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if not use_upload_dir and is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }), 400
        
        # アップロードフォルダの場合はそのまま使用
        if use_upload_dir:
            dir_path = UPLOAD_DIR
        else:
            # Windowsパスの処理: バックスラッシュとスラッシュを正規化
            # c:\\html, c:\html, c:/html を正しく処理
            directory = directory.strip()
            # スラッシュをバックスラッシュに変換（Windowsパスの場合）
            if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
                # Windows絶対パス（例: C:\html, C:/html）
                # ドライブレターを大文字に正規化
                directory = directory[0].upper() + directory[1:].replace('/', '\\')
            else:
                # 相対パスやその他の形式
                directory = directory.replace('\\\\', '\\').replace('/', '\\')
            
            # パスを正規化
            try:
                # Windows絶対パスの場合、Path()で直接処理
                if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                    dir_path = Path(directory)
                else:
                    dir_path = Path(directory).resolve()
            except Exception as e:
                return jsonify({
                    'success': False, 
                    'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
                }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            # より詳細なエラーメッセージ
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if not parent.exists():
                    error_msg += f' (親ディレクトリも存在しません: {parent})'
                else:
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            if not is_cloud:
                error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            else:
                error_msg += f'\nパスの例: /tmp/html または /app/html\nLinux形式の絶対パスを指定してください'
            error_msg += '\n\n💡 ヒント: アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                # ファイル読み込みエラーはスキップ
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}), 400
        
        # 差分を検出
        differences = analyze_differences(parsed_files, options)
        
        # サマリーを生成
        summary = {
            'totalFiles': len(parsed_files),
            'structureDiffs': sum(1 for d in differences if d['type'] == 'structure'),
            'styleDiffs': sum(1 for d in differences if d['type'] == 'style'),
            'contentDiffs': sum(1 for d in differences if d['type'] == 'content'),
            'attributeDiffs': sum(1 for d in differences if d['type'] == 'attribute')
        }
        
        return jsonify({
            'success': True,
            'summary': summary,
            'differences': differences,
            'files': [f['filename'] for f in parsed_files]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def analyze_differences(parsed_files, options):
    """
    HTMLファイル間の差分を分析
    
    処理を最適化するため、以下の制限を設けています:
    - 最大要素数: 1000要素（パフォーマンス向上のため）
    - タイムアウト: 60秒（長時間実行を防ぐため）
    """
    import time
    import signal
    
    differences = []
    
    if len(parsed_files) < 2:
        return differences
    
    # タイムアウト設定（60秒）
    start_time = time.time()
    timeout = 60
    
    # 基準ファイル（最初のファイル）
    base_file = parsed_files[0]
    base_soup = base_file['soup']
    
    # 各要素を比較
    def get_all_elements(soup):
        """すべての要素を取得（最大1000要素に制限）"""
        elements = []
        if soup.body:
            body_elements = soup.body.find_all()
            # 要素数を制限（パフォーマンス向上のため）
            max_elements = 1000
            if len(body_elements) > max_elements:
                # 重要な要素（idやclassを持つ要素）を優先的に取得
                important_elements = [e for e in body_elements if e.get('id') or e.get('class')]
                if len(important_elements) < max_elements:
                    # 重要でない要素も追加
                    other_elements = [e for e in body_elements if not (e.get('id') or e.get('class'))]
                    elements.extend(important_elements)
                    elements.extend(other_elements[:max_elements - len(important_elements)])
                else:
                    elements.extend(important_elements[:max_elements])
            else:
                elements.extend(body_elements)
        if soup.head and options.get('styles', True):
            elements.extend(soup.head.find_all(['style', 'link']))
        return elements
    
    def get_element_signature(elem):
        """要素のシグネチャを取得（比較用）"""
        if not elem or not hasattr(elem, 'name'):
            return None
        
        sig = {
            'tag': elem.name,
            'id': elem.get('id', ''),
            'classes': sorted(elem.get('class', [])) if isinstance(elem.get('class'), list) else [elem.get('class')] if elem.get('class') else []
        }
        return sig
    
    def compare_elements(elem1, elem2):
        """2つの要素を比較"""
        sig1 = get_element_signature(elem1)
        sig2 = get_element_signature(elem2)
        
        if not sig1 or not sig2:
            return False
        
        return sig1['tag'] == sig2['tag'] and sig1['id'] == sig2['id'] and sig1['classes'] == sig2['classes']
    
    # 基準ファイルの要素を取得
    base_elements = get_all_elements(base_soup)
    
    # タイムアウトチェック用のカウンター
    processed_count = 0
    total_elements = len(base_elements)
    
    # 各要素について、他のファイルと比較
    for base_elem in base_elements:
        # タイムアウトチェック
        if time.time() - start_time > timeout:
            differences.append({
                'type': 'system',
                'element': 'timeout',
                'description': f'処理がタイムアウトしました（{timeout}秒）。処理済み: {processed_count}/{total_elements}要素',
                'files': []
            })
            break
        
        processed_count += 1
        
        base_sig = get_element_signature(base_elem)
        if not base_sig:
            continue
        
        # セレクタを生成（最適化: 複雑なセレクタを避ける）
        selector = base_sig['tag']
        if base_sig['id']:
            # IDがある場合はIDセレクタのみを使用（高速）
            selector = f"#{base_sig['id']}"
        elif base_sig['classes']:
            # クラスのみの場合はクラスセレクタを使用
            selector = base_sig['tag'] + '.' + '.'.join(base_sig['classes'][:3])  # 最大3つのクラスのみ使用
        
        # 他のファイルで同じ要素を探す
        matching_files = [base_file['filename']]
        different_files = []
        
        for other_file in parsed_files[1:]:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                break
                
            other_soup = other_file['soup']
            try:
                # セレクタが複雑な場合は、より単純な方法で検索
                if base_sig['id']:
                    found = other_soup.find(id=base_sig['id'])
                elif base_sig['classes']:
                    found = other_soup.find(base_sig['tag'], class_=base_sig['classes'][0] if base_sig['classes'] else None)
                else:
                    found = other_soup.select_one(selector) if selector else None
                if found:
                    matching_files.append(other_file['filename'])
                    
                    # 構造の差分をチェック
                    if options.get('structure', True):
                        if found.name != base_elem.name:
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'structure',
                                'message': f"タグ名が異なります: {found.name} vs {base_elem.name}"
                            })
                    
                    # 属性の差分をチェック
                    if options.get('attributes', True):
                        base_attrs = set(base_elem.attrs.keys())
                        found_attrs = set(found.attrs.keys())
                        
                        # 追加された属性
                        added = found_attrs - base_attrs
                        # 削除された属性
                        removed = base_attrs - found_attrs
                        # 値が異なる属性
                        different = []
                        for attr in base_attrs & found_attrs:
                            if base_elem.get(attr) != found.get(attr):
                                different.append(attr)
                        
                        if added or removed or different:
                            diff_msg = []
                            if added:
                                diff_msg.append(f"追加: {', '.join(added)}")
                            if removed:
                                diff_msg.append(f"削除: {', '.join(removed)}")
                            if different:
                                diff_msg.append(f"変更: {', '.join(different)}")
                            
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'attribute',
                                'message': '; '.join(diff_msg)
                            })
                    
                    # コンテンツの差分をチェック
                    if options.get('content', True):
                        base_text = base_elem.get_text(strip=True)
                        found_text = found.get_text(strip=True)
                        
                        if base_text != found_text:
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'content',
                                'message': f"テキストが異なります"
                            })
                else:
                    # 要素が見つからない
                    if options.get('structure', True):
                        different_files.append({
                            'file': other_file['filename'],
                            'type': 'structure',
                            'message': '要素が見つかりません'
                        })
            except Exception as e:
                # セレクタが無効な場合はスキップ
                # エラーをログに記録しない（パフォーマンス向上のため）
                pass
        
        # 差分がある場合は記録（最大1000件に制限）
        if different_files and len(differences) < 1000:
            diff_type = different_files[0]['type']
            affected_files = [df['file'] for df in different_files]
            
            differences.append({
                'type': diff_type,
                'element': selector,
                'description': different_files[0]['message'] if different_files else '差分が検出されました',
                'files': affected_files,
                'matchingFiles': matching_files
            })
        
        # 差分が多すぎる場合は早期終了
        if len(differences) >= 1000:
            differences.append({
                'type': 'system',
                'element': 'limit',
                'description': f'差分が多すぎるため、処理を中断しました（最大1000件）。処理済み: {processed_count}/{total_elements}要素',
                'files': []
            })
            break
    
    # スタイルの差分をチェック（タイムアウトチェック付き）
    if options.get('styles', True) and time.time() - start_time < timeout:
        base_styles = []
        if base_soup.head:
            base_styles.extend(base_soup.head.find_all('style'))
            base_styles.extend(base_soup.head.find_all('link', rel='stylesheet'))
        
        for other_file in parsed_files[1:]:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                break
                
            other_soup = other_file['soup']
            other_styles = []
            if other_soup.head:
                other_styles.extend(other_soup.head.find_all('style'))
                other_styles.extend(other_soup.head.find_all('link', rel='stylesheet'))
            
            if len(base_styles) != len(other_styles):
                differences.append({
                    'type': 'style',
                    'element': 'head > style/link',
                    'description': f"スタイルシートの数が異なります: {len(base_styles)} vs {len(other_styles)}",
                    'files': [other_file['filename']]
                })
    
    return differences


@app.route('/gcd-template', methods=['POST'])
def gcd_template():
    """差分を含めて最大公約数的な共通テンプレートを生成"""
    try:
        data = request.json
        directory = data.get('directory', '')
        options = data.get('options', {})
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        # ディレクトリの存在確認
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return jsonify({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}), 404
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                # ファイル読み込みエラーはスキップ
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}), 400
        
        # 最大公約数テンプレートを生成
        gcd_template, stats = generate_gcd_template(parsed_files, options)
        
        return jsonify({
            'success': True,
            'template': gcd_template,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def generate_gcd_template(parsed_files, options):
    """差分を含めて最大公約数的なテンプレートを生成"""
    if not parsed_files:
        return '', {
            'totalFiles': 0,
            'commonElements': 0,
            'variableElements': 0,
            'mergedElements': 0,
            'variables': []
        }
    
    # 最初のファイルを基準にする
    base_soup = parsed_files[0]['soup'].__class__(str(parsed_files[0]['soup']), 'html.parser')
    base_soup = BeautifulSoup(str(base_soup), 'html.parser')
    
    stats = {
        'totalFiles': len(parsed_files),
        'commonElements': 0,
        'variableElements': 0,
        'mergedElements': 0,
        'variables': []
    }
    
    variable_counter = 1
    
    def get_element_path(elem):
        """要素のパスを取得"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        path = []
        current = elem
        while current and hasattr(current, 'name') and current.name:
            selector = current.name
            if hasattr(current, 'attrs'):
                if 'id' in current.attrs:
                    selector += f"#{current.attrs['id']}"
                elif 'class' in current.attrs:
                    classes = current.attrs['class']
                    if isinstance(classes, list) and classes:
                        selector += '.' + '.'.join(classes[:1])
            path.insert(0, selector)
            current = current.parent if hasattr(current, 'parent') else None
            if current == base_soup or current == base_soup.html or current == base_soup.body:
                break
        return ' > '.join(path)
    
    def merge_element_gcd(base_elem, other_files, path=''):
        """要素を最大公約数的に統合"""
        if not base_elem or not hasattr(base_elem, 'name'):
            return base_elem
        
        current_path = path + ' > ' + base_elem.name if path else base_elem.name
        
        # 他のファイルで同じ要素を探す
        matching_elements = [base_elem]
        base_selector = get_element_selector_for_gcd(base_elem)
        
        for other_data in other_files:
            other_soup = other_data['soup']
            try:
                found = other_soup.select_one(base_selector)
                if found:
                    matching_elements.append(found)
            except Exception:
                pass
        
        # すべてのファイルで見つかった場合
        if len(matching_elements) == len(other_files) + 1:
            # 属性を統合
            if options.get('attributes', True):
                all_attrs = {}
                attr_values = {}
                
                # すべての要素の属性を収集
                for elem in matching_elements:
                    if hasattr(elem, 'attrs'):
                        for key, value in elem.attrs.items():
                            if key not in all_attrs:
                                all_attrs[key] = []
                            if key not in attr_values:
                                attr_values[key] = []
                            
                            if isinstance(value, list):
                                all_attrs[key].extend(value)
                                attr_values[key].append(tuple(sorted(value)))
                            else:
                                all_attrs[key].append(value)
                                attr_values[key].append(value)
                
                # 共通属性を決定
                common_attrs = {}
                variable_attrs = {}
                
                for key, values in attr_values.items():
                    unique_values = set(str(v) for v in values)
                    if len(unique_values) == 1:
                        # すべて同じ値
                        common_attrs[key] = matching_elements[0].attrs[key]
                        stats['commonElements'] += 1
                    else:
                        # 値が異なる場合は変数化
                        var_name = f"VAR_ATTR_{variable_counter}"
                        variable_counter += 1
                        variable_attrs[key] = var_name
                        stats['variableElements'] += 1
                        stats['variables'].append({
                            'name': var_name,
                            'type': 'attribute',
                            'element': current_path,
                            'description': f"属性 '{key}' の値（複数の値が存在: {', '.join(list(unique_values)[:3])}）"
                        })
                        # 最初の値をデフォルトとして使用
                        common_attrs[key] = matching_elements[0].attrs[key]
                
                # 共通属性を設定
                base_elem.attrs.clear()
                base_elem.attrs.update(common_attrs)
                
                # 変数化された属性をコメントとして追加
                if variable_attrs:
                    comment_text = "<!-- "
                    for key, var_name in variable_attrs.items():
                        comment_text += f"{var_name}={key}; "
                    comment_text += "-->"
                    if hasattr(base_elem, 'insert'):
                        base_elem.insert(0, BeautifulSoup(comment_text, 'html.parser'))
            
            # テキストコンテンツを統合
            if options.get('content', True):
                texts = []
                for elem in matching_elements:
                    try:
                        if hasattr(elem, 'get_text'):
                            text = elem.get_text(strip=True)
                            if text:
                                texts.append(text)
                    except Exception:
                        pass
                
                if texts:
                    unique_texts = set(texts)
                    if len(unique_texts) == 1:
                        # すべて同じテキスト
                        stats['commonElements'] += 1
                    else:
                        # テキストが異なる場合は変数化
                        var_name = f"VAR_TEXT_{variable_counter}"
                        variable_counter += 1
                        stats['variableElements'] += 1
                        stats['variables'].append({
                            'name': var_name,
                            'type': 'content',
                            'element': current_path,
                            'description': f"テキスト内容（複数の値が存在: {', '.join(list(unique_texts)[:3])}）"
                        })
                        
                        # テキストを変数プレースホルダーに置換
                        try:
                            if hasattr(base_elem, 'string') and base_elem.string:
                                base_elem.string = f"{{{{ {var_name} }}}}"
                            else:
                                # 子要素をクリアして変数を挿入
                                for child in list(base_elem.children):
                                    if hasattr(child, 'get_text') and child.get_text(strip=True):
                                        child.decompose()
                                base_elem.append(BeautifulSoup(f"{{{{ {var_name} }}}}", 'html.parser'))
                        except Exception:
                            pass
            
            # 子要素を再帰的に統合
            if hasattr(base_elem, 'children'):
                for child in list(base_elem.children):
                    if hasattr(child, 'name') and child.name:
                        try:
                            merge_element_gcd(child, other_files, current_path)
                        except Exception:
                            pass
        
        return base_elem
    
    def get_element_selector_for_gcd(elem):
        """要素のセレクタを取得（最大公約数用）"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        selector = elem.name
        
        # IDがあれば追加（IDは一意なので優先）
        if hasattr(elem, 'attrs') and 'id' in elem.attrs:
            selector += f"#{elem.attrs['id']}"
        # クラスがあれば追加（最初のクラスのみ）
        elif hasattr(elem, 'attrs') and 'class' in elem.attrs:
            classes = elem.attrs['class']
            if isinstance(classes, list) and classes:
                selector += '.' + classes[0]
            elif classes:
                selector += f".{classes}"
        
        return selector
    
    # body要素を統合
    if base_soup.body:
        merge_element_gcd(base_soup.body, parsed_files[1:])
    
    # head要素も統合（スタイルなど）
    if options.get('styles', True) and base_soup.head:
        merge_element_gcd(base_soup.head, parsed_files[1:])
    
    # 統計を更新
    stats['mergedElements'] = stats['commonElements'] + stats['variableElements']
    
    # 変数定義セクションを追加
    if stats['variables']:
        if base_soup.head:
            var_section = base_soup.new_tag('script', type='text/template-variables')
            var_section.string = '\n'.join([
                f"// {v['name']}: {v['description']}"
                for v in stats['variables']
            ])
            base_soup.head.append(var_section)
    
    # 統合されたHTMLを生成
    gcd_html = str(base_soup)
    
    return gcd_html, stats


@app.route('/generate-university-pages', methods=['POST'])
def generate_university_pages():
    """テンプレートを基に27大学のホームページを生成"""
    try:
        data = request.json
        directory = data.get('directory', '')
        template = data.get('template', '')
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        if not template:
            return jsonify({'success': False, 'error': 'テンプレートが指定されていません'}), 400
        
        # ディレクトリの存在確認
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return jsonify({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}), 404
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # テンプレートを解析
        template_soup = BeautifulSoup(template, 'html.parser')
        
        # 出力ディレクトリを作成
        output_dir = dir_path / 'generated_pages'
        output_dir.mkdir(exist_ok=True)
        
        generated_files = []
        success_count = 0
        failed_count = 0
        
        # 各大学のファイルを処理
        for file_path in html_files:
            try:
                # 元のファイルを読み込み
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                original_soup = BeautifulSoup(original_content, 'html.parser')
                
                # テンプレートをコピー
                generated_soup = BeautifulSoup(str(template_soup), 'html.parser')
                
                # 元のファイルからデザイン情報を抽出して適用
                apply_design_to_template(generated_soup, original_soup, file_path.name)
                
                # 生成されたHTMLを保存
                output_filename = f"generated_{file_path.stem}.html"
                output_path = output_dir / output_filename
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(str(generated_soup))
                
                generated_files.append(output_filename)
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Error processing {file_path.name}: {str(e)}")
                continue
        
        return jsonify({
            'success': True,
            'generatedFiles': len(generated_files),
            'successCount': success_count,
            'failedCount': failed_count,
            'files': generated_files,
            'directory': str(output_dir)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def get_element_selector_simple(elem):
    """要素のセレクタを取得（シンプル版）"""
    if not elem or not hasattr(elem, 'name'):
        return ''
    
    selector = elem.name
    
    # IDがあれば追加（IDは一意なので優先）
    if hasattr(elem, 'attrs') and 'id' in elem.attrs:
        selector += f"#{elem.attrs['id']}"
    # クラスがあれば追加（最初のクラスのみ）
    elif hasattr(elem, 'attrs') and 'class' in elem.attrs:
        classes = elem.attrs['class']
        if isinstance(classes, list) and classes:
            selector += '.' + classes[0]
        elif classes:
            selector += f".{classes}"
    
    return selector


def apply_design_to_template(template_soup, original_soup, original_filename):
    """元のHTMLからデザイン情報を抽出してテンプレートに適用（現行デザインを完全再現）"""
    import re
    
    # 1. head要素の完全な適用
    if original_soup.head and template_soup.head:
        # 既存のhead要素をクリア（charset以外）
        for child in list(template_soup.head.children):
            if hasattr(child, 'name') and child.name not in ['meta']:
                child.decompose()
            elif hasattr(child, 'name') and child.name == 'meta' and child.get('charset'):
                continue  # charsetは保持
            elif not hasattr(child, 'name'):
                child.decompose()
        
        # 元のhead要素の内容をコピー
        for child in original_soup.head.children:
            if hasattr(child, 'name'):
                if child.name == 'meta' and child.get('charset'):
                    continue  # charsetは既に存在
                
                # 新しい要素を作成
                new_elem = template_soup.new_tag(child.name)
                if hasattr(child, 'attrs'):
                    for attr, value in child.attrs.items():
                        if isinstance(value, list):
                            new_elem[attr] = value
                        else:
                            new_elem[attr] = value
                
                if hasattr(child, 'string') and child.string:
                    new_elem.string = child.string
                elif hasattr(child, 'contents'):
                    for content in child.contents:
                        if hasattr(content, 'name'):
                            new_elem.append(content)
                        else:
                            new_elem.append(str(content))
                
                template_soup.head.append(new_elem)
    
    # 2. body要素の構造を保持しながらデザインを適用
    def apply_element_design(template_elem, original_elem):
        """要素のデザインを適用"""
        if not template_elem or not original_elem:
            return
        
        # すべての属性を適用（クラス、ID、data属性など）
        if hasattr(original_elem, 'attrs'):
            for attr_name, attr_value in original_elem.attrs.items():
                if attr_name not in ['id'] or template_elem.get('id') != attr_value:
                    if isinstance(attr_value, list):
                        template_elem[attr_name] = attr_value
                    else:
                        template_elem[attr_name] = attr_value
        
        # インラインスタイルを適用
        if original_elem.get('style'):
            template_elem['style'] = original_elem.get('style')
        
        # テキストコンテンツを適用（変数が含まれていない場合）
        if hasattr(original_elem, 'get_text') and hasattr(template_elem, 'string'):
            original_text = original_elem.get_text(strip=True)
            template_text = str(template_elem.string) if template_elem.string else ''
            
            # 変数が含まれていない場合は元のテキストを適用
            if '{{' not in template_text and '}}' not in template_text:
                if original_text and not any(hasattr(c, 'name') for c in template_elem.children if hasattr(c, 'name')):
                    template_elem.string = original_text
    
    # 3. 変数を元の値で置換
    def replace_variables(elem):
        """変数プレースホルダーを元の値で置換"""
        if not elem:
            return
        
        # テキスト内の変数を置換
        if hasattr(elem, 'string') and elem.string:
            text = str(elem.string)
            if '{{' in text and '}}' in text:
                var_matches = re.findall(r'\{\{\s*(\w+)\s*\}\}', text)
                for var_name in var_matches:
                    original_value = find_original_value(original_soup, var_name, elem)
                    if original_value:
                        elem.string = text.replace(f"{{{{ {var_name} }}}}", str(original_value))
        
        # 属性内の変数を置換
        if hasattr(elem, 'attrs'):
            for attr_name, attr_value in list(elem.attrs.items()):
                if isinstance(attr_value, str) and '{{' in attr_value and '}}' in attr_value:
                    var_matches = re.findall(r'\{\{\s*(\w+)\s*\}\}', attr_value)
                    for var_name in var_matches:
                        original_value = find_original_value(original_soup, var_name, elem, attr_name)
                        if original_value:
                            elem.attrs[attr_name] = attr_value.replace(f"{{{{ {var_name} }}}}", str(original_value))
        
        # 子要素を再帰的に処理
        if hasattr(elem, 'children'):
            for child in list(elem.children):
                if hasattr(child, 'name'):
                    replace_variables(child)
    
    # 4. 元のHTMLから対応する要素を探して値を取得
    def find_original_value(original_soup, var_name, template_elem, attr_name=None):
        """元のHTMLから変数に対応する値を探す"""
        selector = get_element_selector_simple(template_elem)
        
        try:
            original_elem = original_soup.select_one(selector)
            if original_elem:
                if attr_name:
                    return original_elem.get(attr_name, '')
                else:
                    return original_elem.get_text(strip=True)
        except Exception:
            pass
        
        return None
    
    # 5. body要素の各要素に対してデザインを適用
    if original_soup.body and template_soup.body:
        # 元のbody要素のすべての要素を取得
        original_elems = original_soup.body.find_all(True)
        
        for orig_elem in original_elems:
            selector = get_element_selector_simple(orig_elem)
            
            try:
                # テンプレート内で対応する要素を探す
                template_elems = template_soup.body.select(selector)
                
                if template_elems:
                    # 最初のマッチした要素にデザインを適用
                    apply_element_design(template_elems[0], orig_elem)
                else:
                    # 要素が見つからない場合は、親要素を探して追加
                    # （構造が異なる場合のフォールバック）
                    pass
            except Exception:
                pass
    
    # 6. 変数を置換
    if template_soup.body:
        replace_variables(template_soup.body)
    
    # 7. body要素の属性を適用（class、id、styleなど）
    if original_soup.body and template_soup.body:
        for attr_name, attr_value in original_soup.body.attrs.items():
            if attr_name not in ['id']:  # idは保持
                template_soup.body[attr_name] = attr_value


@app.route('/download-university-pages', methods=['POST'])
def download_university_pages():
    """生成された27大学のホームページをZIPファイルでダウンロード"""
    try:
        data = request.json
        directory = data.get('directory', '')
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        # 出力ディレクトリ
        output_dir = Path(directory) / 'generated_pages'
        
        if not output_dir.exists():
            return jsonify({'success': False, 'error': '生成されたファイルが見つかりません'}), 404
        
        # 一時ZIPファイルを作成
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        # ZIPファイルを作成
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_dir.glob('*.html'):
                zipf.write(file_path, file_path.name)
        
        return send_file(
            temp_zip.name,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'university_pages_{Path(directory).name}.zip'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/template-merge', methods=['POST', 'OPTIONS'])
def template_merge():
    """複数のHTMLファイルを比較して共通テンプレートを生成"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        files = data.get('files', [])
        options = data.get('options', {})
        
        if len(files) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを選択してください'}), 400
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path_str in files:
            # ファイルパスが絶対パスか相対パスかを判定
            file_path = Path(file_path_str)
            
            # 絶対パスでない場合、アップロードフォルダからの相対パスとして扱う
            if not file_path.is_absolute():
                safe_filename = secure_filename(file_path_str)
                file_path = UPLOAD_DIR / safe_filename
            
            if not file_path.exists():
                return jsonify({'success': False, 'error': f'ファイルが見つかりません: {file_path_str}'}), 404
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                return jsonify({'success': False, 'error': f'ファイルの読み込みに失敗しました: {file_path_str} - {str(e)}'}), 500
            
            try:
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                return jsonify({'success': False, 'error': f'ファイルの解析エラー ({filename}): {str(e)}'}), 400
        
        # 共通テンプレートを生成
        merged_template, stats = merge_html_templates(parsed_files, options)
        
        return jsonify({
            'success': True,
            'template': merged_template,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/list-directory-files', methods=['POST', 'OPTIONS'])
def list_directory_files():
    """指定ディレクトリ内のファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        # 空欄の場合はアップロードフォルダを使用
        if not directory:
            directory = str(UPLOAD_DIR)
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。\n'
                        f'または、Linux形式の絶対パス（例: /tmp/html）を指定してください。'
            }), 400
        
        # Windowsパスの処理: バックスラッシュとスラッシュを正規化
        # c:\\html, c:\html, c:/html を正しく処理
        directory = directory.strip()
        # スラッシュをバックスラッシュに変換（Windowsパスの場合）
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            # Windows絶対パス（例: C:\html, C:/html）
            # ドライブレターを大文字に正規化
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            # 相対パスやその他の形式
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        # パスを正規化
        try:
            # Windows絶対パスの場合、Path()で直接処理
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if parent.exists():
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # すべてのファイルを検索（HTML、CSS、その他）
        files = []
        
        # HTMLファイル（識別子情報も抽出）
        for ext in ['*.html', '*.htm']:
            for file_path in dir_path.glob(ext):
                try:
                    file_info = {
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': 'html'
                    }
                    
                    # HTMLファイル内の識別子を抽出
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # IDを抽出
                        ids = set()
                        for elem in soup.find_all(id=True):
                            elem_id = elem.get('id')
                            if elem_id:
                                ids.add(str(elem_id))
                        
                        # クラス名を抽出
                        classes = set()
                        for elem in soup.find_all(class_=True):
                            elem_classes = elem.get('class', [])
                            if isinstance(elem_classes, list):
                                classes.update([str(c) for c in elem_classes if c])
                            elif elem_classes:
                                classes.add(str(elem_classes))
                        
                        # データ属性を抽出
                        data_attrs = set()
                        for elem in soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys())):
                            for attr in elem.attrs:
                                if attr.startswith('data-'):
                                    data_attrs.add(attr)
                        
                        file_info['identifiers'] = {
                            'ids': sorted(list(ids)),
                            'classes': sorted(list(classes)),
                            'data_attrs': sorted(list(data_attrs))
                        }
                    except Exception as e:
                        # HTML解析エラーは無視（識別子情報なしで続行）
                        file_info['identifiers'] = {
                            'ids': [],
                            'classes': [],
                            'data_attrs': []
                        }
                    
                    files.append(file_info)
                except Exception:
                    continue
        
        # CSSファイル
        for file_path in dir_path.glob('*.css'):
            try:
                files.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'type': 'css'
                })
            except Exception:
                continue
        
        # その他のテキストファイル（オプション）
        for ext in ['*.txt', '*.js', '*.json', '*.xml']:
            for file_path in dir_path.glob(ext):
                try:
                    files.append({
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': 'other'
                    })
                except Exception:
                    continue
        
        # ファイル名でソート
        files.sort(key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """アプリケーション設定を取得"""
    try:
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        
        return jsonify({
            'success': True,
            'is_cloud': bool(is_cloud),
            'default_html_directory': None,
            'upload_folder': app.config.get('UPLOAD_FOLDER', 'uploads'),
            'directory_info': None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-directory', methods=['POST', 'OPTIONS'])
def check_directory():
    """指定されたディレクトリの存在確認とファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスを指定してください'}), 400
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\nLinux形式の絶対パス（例: /tmp/html）を指定してください。'
            }), 400
        
        # パスの正規化
        try:
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                # Windows絶対パス
                directory = directory[0].upper() + directory[1:].replace('/', '\\')
                dir_path = Path(directory)
            else:
                # Linux形式のパス
                dir_path = Path(directory)
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        exists = dir_path.exists() and dir_path.is_dir()
        
        result = {
            'success': True,
            'directory': directory,
            'exists': exists,
            'is_absolute': dir_path.is_absolute(),
            'parent_exists': dir_path.parent.exists() if dir_path.parent != dir_path else False,
            'parent_path': str(dir_path.parent) if dir_path.parent != dir_path else None
        }
        
        if exists:
            # ファイル一覧を取得
            files = []
            try:
                for file_path in dir_path.iterdir():
                    if file_path.is_file():
                        files.append({
                            'name': file_path.name,
                            'size': file_path.stat().st_size,
                            'modified': file_path.stat().st_mtime
                        })
                result['file_count'] = len(files)
                result['files'] = files[:50]  # 最大50件まで
            except Exception as e:
                result['error'] = f'ファイル一覧の取得に失敗: {str(e)}'
        else:
            result['file_count'] = 0
            result['files'] = []
            if dir_path.parent.exists():
                result['suggestion'] = f'親ディレクトリ（{dir_path.parent}）は存在します。ディレクトリが作成されていない可能性があります。'
            else:
                result['suggestion'] = '指定されたパスとその親ディレクトリが存在しません。'
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load-comparison-files', methods=['POST', 'OPTIONS'])
def load_comparison_files():
    """比較用ファイルリストを読み込む"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        # 空欄の場合はアップロードフォルダを使用
        if not directory:
            directory = str(UPLOAD_DIR)
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }), 400
        
        # Windowsパスの処理: バックスラッシュとスラッシュを正規化
        # c:\\html, c:\html, c:/html を正しく処理
        directory = directory.strip()
        # スラッシュをバックスラッシュに変換（Windowsパスの場合）
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            # Windows絶対パス（例: C:\html, C:/html）
            # ドライブレターを大文字に正規化
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            # 相対パスやその他の形式
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        # パスを正規化
        try:
            # Windows絶対パスの場合、Path()で直接処理
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            # より詳細なエラーメッセージ
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if not parent.exists():
                    error_msg += f' (親ディレクトリも存在しません: {parent})'
                else:
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            if not is_cloud:
                error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            else:
                error_msg += f'\nパスの例: /tmp/html または /app/html\nLinux形式の絶対パスを指定してください'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # HTMLファイルとCSSファイルを検索（最大27個）
        html_files = []
        css_files = []
        
        for ext in ['*.html', '*.htm']:
            html_files.extend(dir_path.glob(ext))
            html_files.extend(dir_path.glob(ext.upper()))
        
        for ext in ['*.css']:
            css_files.extend(dir_path.glob(ext))
            css_files.extend(dir_path.glob(ext.upper()))
        
        # ファイル名でソート
        html_files = sorted(html_files, key=lambda x: x.name)[:27]
        css_files = sorted(css_files, key=lambda x: x.name)
        
        # HTMLファイルとCSSファイルの関連付け
        html_css_map = {}
        for css_file in css_files:
            css_name = css_file.stem  # 拡張子なしのファイル名
            for html_file in html_files:
                html_name = html_file.stem
                # ファイル名が一致するか、HTMLファイル内で参照されているか確認
                if css_name == html_name or css_name in html_name or html_name in css_name:
                    if html_file.path not in html_css_map:
                        html_css_map[html_file.path] = []
                    html_css_map[html_file.path].append(str(css_file))
        
        files = []
        for file_path in html_files:
            try:
                size = file_path.stat().st_size
                related_css = html_css_map.get(str(file_path), [])
                files.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': size,
                    'type': 'html',
                    'relatedFiles': related_css
                })
            except Exception as e:
                continue
        
        # CSSファイルも追加（HTMLに関連付けられていないものも含む）
        for css_file in css_files:
            try:
                size = css_file.stat().st_size
                # 既にHTMLに関連付けられているCSSはスキップ（重複を避ける）
                is_related = any(str(css_file) in file.get('relatedFiles', []) for file in files)
                if not is_related:
                    files.append({
                        'name': css_file.name,
                        'path': str(css_file),
                        'size': size,
                        'type': 'css',
                        'relatedFiles': []
                    })
            except Exception as e:
                continue
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load-file-content', methods=['GET'])
def load_file_content():
    """ファイルの内容を読み込む"""
    try:
        file_path = request.args.get('path', '')
        if not file_path:
            return jsonify({'success': False, 'error': 'ファイルパスを指定してください'}), 400
        
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # セキュリティチェック：指定されたディレクトリ内のファイルのみ許可
        # ここでは簡易的に実装（本番環境ではより厳密なチェックが必要）
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'filename': path.name
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/compare-screens', methods=['POST', 'OPTIONS'])
def compare_screens():
    """複数の画面を比較して差分を検出"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        file_paths = data.get('files', [])
        
        if len(file_paths) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを指定してください'}), 400
        
        # 各ファイルを読み込んで解析
        parsed_files = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'path': file_path,
                    'name': path.name,
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '有効なファイルが2つ以上必要です'}), 400
        
        # 比較分析を実行（HTMLとCSSの両方）
        comparison = {}
        base_file = parsed_files[0]
        
        # ベースファイルのCSSを抽出
        base_css = extract_css_from_html(base_file['soup'])
        
        for file_info in parsed_files[1:]:
            # HTML構造の比較
            html_differences = compare_html_structure(base_file['soup'], file_info['soup'])
            
            # CSSの比較
            file_css = extract_css_from_html(file_info['soup'])
            css_differences = []
            
            # インラインCSSの比較
            if base_css['inline_css'] or file_css['inline_css']:
                css_diffs = compare_css(base_css['inline_css'], file_css['inline_css'])
                css_differences.extend(css_diffs)
            
            # すべての差分を統合
            all_differences = html_differences + css_differences
            
            comparison[file_info['path']] = {
                'differences': len(all_differences),
                'htmlDifferences': len(html_differences),
                'cssDifferences': len(css_differences),
                'details': all_differences[:20]  # 最初の20件
            }
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'base_file': base_file['name']
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def extract_css_from_html(soup):
    """HTMLからCSSを抽出"""
    css_content = []
    
    # <style>タグ内のCSS
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            css_content.append(style_tag.string)
    
    # <link rel="stylesheet">で参照されているCSSファイル
    css_files = []
    for link_tag in soup.find_all('link', rel='stylesheet'):
        href = link_tag.get('href', '')
        if href:
            css_files.append(href)
    
    return {
        'inline_css': '\n'.join(css_content),
        'external_css': css_files
    }


def parse_css(css_content):
    """CSSをパースしてルールを抽出"""
    import re
    if not css_content or not css_content.strip():
        return []
    
    rules = []
    
    # メディアクエリを処理
    media_pattern = r'@media[^{]*\{'
    media_blocks = re.split(media_pattern, css_content)
    current_media = None
    
    for i, block in enumerate(media_blocks):
        if i == 0 and '@media' in block:
            # 最初のブロックがメディアクエリの場合
            media_match = re.search(r'@media\s+([^{]+)', block)
            if media_match:
                current_media = media_match.group(1).strip()
            continue
        
        # セレクタとプロパティを抽出
        selector_pattern = r'([^{]+)\{([^}]+)\}'
        matches = re.finditer(selector_pattern, block)
        
        for match in matches:
            selector = match.group(1).strip()
            properties_str = match.group(2).strip()
            
            # プロパティをパース
            properties = {}
            prop_matches = re.finditer(r'([^:]+):\s*([^;]+);?', properties_str)
            for prop_match in prop_matches:
                key = prop_match.group(1).strip()
                value = prop_match.group(2).strip()
                properties[key] = value
            
            if selector:  # 空のセレクタは無視
                rules.append({
                    'selector': selector,
                    'properties': properties,
                    'media': current_media
                })
        
        # メディアクエリのリセット
        if '@media' in block:
            media_match = re.search(r'@media\s+([^{]+)', block)
            if media_match:
                current_media = media_match.group(1).strip()
            else:
                current_media = None
    
    return rules


def compare_css(css1_content, css2_content):
    """2つのCSSを比較して差分を返す"""
    if not css1_content and not css2_content:
        return []
    
    rules1 = parse_css(css1_content) if css1_content else []
    rules2 = parse_css(css2_content) if css2_content else []
    
    differences = []
    
    # セレクタごとに比較
    selectors1 = {rule['selector']: rule for rule in rules1}
    selectors2 = {rule['selector']: rule for rule in rules2}
    
    all_selectors = set(selectors1.keys()) | set(selectors2.keys())
    
    for selector in all_selectors:
        rule1 = selectors1.get(selector)
        rule2 = selectors2.get(selector)
        
        if not rule1:
            differences.append({
                'type': 'missing',
                'path': f"CSS: {selector}",
                'selector': selector,
                'fileType': 'css'
            })
        elif not rule2:
            differences.append({
                'type': 'extra',
                'path': f"CSS: {selector}",
                'selector': selector,
                'fileType': 'css'
            })
        else:
            # プロパティを比較
            props1 = rule1.get('properties', {})
            props2 = rule2.get('properties', {})
            
            all_props = set(props1.keys()) | set(props2.keys())
            prop_diffs = {}
            
            for prop in all_props:
                val1 = props1.get(prop)
                val2 = props2.get(prop)
                
                if val1 != val2:
                    prop_diffs[prop] = {'old': val1, 'new': val2}
            
            if prop_diffs:
                differences.append({
                    'type': 'different',
                    'path': f"CSS: {selector}",
                    'selector': selector,
                    'properties': prop_diffs,
                    'fileType': 'css'
                })
    
    return differences


def compare_html_structure(soup1, soup2):
    """2つのHTML構造を比較して差分を返す"""
    differences = []
    
    # 簡易的な比較（タグ、クラス、ID、主要な属性）
    def get_element_signature(elem):
        if not elem or not hasattr(elem, 'name'):
            return None
        sig = {
            'tag': elem.name,
            'id': elem.get('id', ''),
            'classes': sorted(elem.get('class', [])),
            'text_length': len(elem.get_text(strip=True))
        }
        return sig
    
    def compare_elements(elems1, elems2, path=''):
        max_len = max(len(elems1), len(elems2))
        for i in range(max_len):
            if i >= len(elems1):
                differences.append({
                    'type': 'missing',
                    'path': f"{path}[{i}]",
                    'element': str(elems2[i])[:100] if i < len(elems2) else ''
                })
            elif i >= len(elems2):
                differences.append({
                    'type': 'extra',
                    'path': f"{path}[{i}]",
                    'element': str(elems1[i])[:100]
                })
            else:
                sig1 = get_element_signature(elems1[i])
                sig2 = get_element_signature(elems2[i])
                
                if sig1 != sig2:
                    differences.append({
                        'type': 'different',
                        'path': f"{path}[{i}]",
                        'element1': sig1,
                        'element2': sig2
                    })
                
                # 再帰的に子要素を比較
                if hasattr(elems1[i], 'children') and hasattr(elems2[i], 'children'):
                    compare_elements(
                        [c for c in elems1[i].children if hasattr(c, 'name')],
                        [c for c in elems2[i].children if hasattr(c, 'name')],
                        f"{path}[{i}]"
                    )
    
    # body要素を比較
    body1 = soup1.find('body')
    body2 = soup2.find('body')
    
    if body1 and body2:
        compare_elements(
            [c for c in body1.children if hasattr(c, 'name')],
            [c for c in body2.children if hasattr(c, 'name')],
            'body'
        )
    
    return differences


@app.route('/api/export-comparison-report', methods=['POST'])
def export_comparison_report():
    """比較レポートをCSV形式でエクスポート"""
    try:
        data = request.json
        files = data.get('files', [])
        
        if len(files) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを指定してください'}), 400
        
        # CSVレポートを生成
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow(['ファイル名', 'タイプ', 'パス', 'サイズ (KB)', '要素数', 'リンク数', '画像数', 'CSSルール数', 'インラインCSS', '外部CSS'])
        
        # 各ファイルの情報
        for file_info in files:
            path = Path(file_info['path'])
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    file_type = file_info.get('type', 'other')
                    size_kb = path.stat().st_size / 1024
                    
                    if file_type == 'html':
                        soup = BeautifulSoup(content, 'html.parser')
                        elements = len(soup.find_all())
                        links = len(soup.find_all('a'))
                        images = len(soup.find_all('img'))
                        
                        # CSS情報を抽出
                        css_info = extract_css_from_html(soup)
                        inline_css_rules = parse_css(css_info['inline_css'])
                        external_css_count = len(css_info['external_css'])
                        
                        writer.writerow([
                            file_info['name'],
                            'HTML',
                            file_info['path'],
                            f"{size_kb:.2f}",
                            elements,
                            links,
                            images,
                            len(inline_css_rules),
                            'あり' if css_info['inline_css'] else 'なし',
                            external_css_count
                        ])
                    elif file_type == 'css':
                        css_rules = parse_css(content)
                        writer.writerow([
                            file_info['name'],
                            'CSS',
                            file_info['path'],
                            f"{size_kb:.2f}",
                            '',
                            '',
                            '',
                            len(css_rules),
                            '',
                            ''
                        ])
                    else:
                        writer.writerow([
                            file_info['name'],
                            file_type.upper(),
                            file_info['path'],
                            f"{size_kb:.2f}",
                            '',
                            '',
                            '',
                            '',
                            '',
                            ''
                        ])
                except Exception as e:
                    writer.writerow([file_info['name'], file_info.get('type', 'other'), file_info['path'], 'エラー', '', '', '', '', '', ''])
        
        return jsonify({
            'success': True,
            'report': output.getvalue()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def merge_html_templates(parsed_files, options):
    """HTMLテンプレートを統合する"""
    if not parsed_files:
        return '', {'commonElements': 0, 'diffElements': 0, 'mergedElements': 0, 'differences': []}
    
    # 最初のファイルを基準にする
    base_soup = parsed_files[0]['soup']
    base_filename = parsed_files[0]['filename']
    
    stats = {
        'commonElements': 0,
        'diffElements': 0,
        'mergedElements': 0,
        'differences': []
    }
    
    # ヘルパー関数を先に定義
    def get_element_selector(elem):
        """要素のセレクタを取得"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        selector = elem.name
        
        # IDがあれば追加
        if hasattr(elem, 'attrs') and 'id' in elem.attrs:
            selector += f"#{elem.attrs['id']}"
        
        # クラスがあれば追加
        if hasattr(elem, 'attrs') and 'class' in elem.attrs:
            classes = elem.attrs['class']
            if isinstance(classes, list):
                selector += '.' + '.'.join(classes)
            else:
                selector += f".{classes}"
        
        return selector
    
    def normalize_element(elem):
        """要素を正規化（比較用）"""
        if not elem or not hasattr(elem, 'name'):
            return None
        
        normalized = {
            'tag': elem.name,
            'attrs': dict(elem.attrs) if hasattr(elem, 'attrs') else {},
            'text': elem.get_text(strip=True) if hasattr(elem, 'get_text') else ''
        }
        
        # クラスをソート（順序の違いを無視）
        if 'class' in normalized['attrs']:
            normalized['attrs']['class'] = sorted(normalized['attrs']['class']) if isinstance(normalized['attrs']['class'], list) else [normalized['attrs']['class']]
        
        return normalized
    
    def compare_elements(elem1, elem2):
        """2つの要素を比較"""
        norm1 = normalize_element(elem1)
        norm2 = normalize_element(elem2)
        
        if not norm1 or not norm2:
            return False
        
        # タグ名が同じか
        if norm1['tag'] != norm2['tag']:
            return False
        
        # 属性を比較（オプションに応じて）
        if options.get('attributes', True):
            # IDが異なる場合は別要素
            if norm1['attrs'].get('id') != norm2['attrs'].get('id'):
                return False
            
            # クラスを比較（順序は無視）
            class1 = set(norm1['attrs'].get('class', []))
            class2 = set(norm2['attrs'].get('class', []))
            if class1 != class2:
                return False
        
        return True
    
    def merge_element(base_elem, other_files):
        """要素を統合"""
        if not base_elem or not hasattr(base_elem, 'name'):
            return base_elem
        
        # 他のファイルで同じ要素を探す
        matching_elements = [base_elem]
        base_selector = get_element_selector(base_elem)
        
        for other_data in other_files:
            other_soup = other_data['soup']
            try:
                # セレクタで要素を検索
                found = other_soup.select_one(base_selector)
                if found and compare_elements(base_elem, found):
                    matching_elements.append(found)
            except Exception as e:
                # セレクタが無効な場合はスキップ
                pass
        
        # 共通属性を抽出
        if options.get('attributes', True) and matching_elements:
            common_attrs = {}
            if len(matching_elements) == len(other_files) + 1:  # すべてのファイルで見つかった
                # 最初の要素の属性を基準に、共通する属性のみを採用
                base_attrs = dict(matching_elements[0].attrs)
                for key, value in base_attrs.items():
                    # すべての要素で同じ値を持つ属性のみ採用
                    if all(hasattr(elem, 'attrs') and elem.attrs.get(key) == value for elem in matching_elements):
                        common_attrs[key] = value
                    else:
                        stats['differences'].append(f"属性 '{key}' が異なります ({base_selector})")
                        stats['diffElements'] += 1
                
                # 共通属性を設定
                matching_elements[0].attrs.clear()
                matching_elements[0].attrs.update(common_attrs)
                stats['commonElements'] += 1
            else:
                stats['diffElements'] += 1
        
        # 子要素を再帰的に統合
        if hasattr(base_elem, 'children'):
            for child in list(base_elem.children):
                if hasattr(child, 'name') and child.name:
                    try:
                        merge_element(child, other_files)
                    except Exception:
                        # エラーが発生した場合はスキップ
                        pass
            
            # 差異がある子要素を処理
            for other_data in other_files:
                other_soup = other_data['soup']
                try:
                    other_elem = other_soup.select_one(base_selector)
                    if other_elem and hasattr(other_elem, 'children'):
                        base_children_tags = [c.name for c in base_elem.children if hasattr(c, 'name') and c.name]
                        other_children_tags = [c.name for c in other_elem.children if hasattr(c, 'name') and c.name]
                        
                        if base_children_tags != other_children_tags:
                            stats['differences'].append(f"子要素の構造が異なります ({base_selector})")
                except Exception:
                    pass
        
        # テキストコンテンツを統合
        if options.get('content', True) and matching_elements:
            texts = []
            for elem in matching_elements:
                try:
                    if hasattr(elem, 'get_text'):
                        texts.append(elem.get_text(strip=True))
                except Exception:
                    pass
            
            if texts:
                # すべて同じテキストの場合のみ採用
                if len(set(texts)) == 1:
                    stats['commonElements'] += 1
                else:
                    # 差異がある場合は、オプションに応じて処理
                    diff_handling = options.get('diffHandling', 'common')
                    if diff_handling == 'common':
                        # 共通部分のみ採用（空にする）
                        try:
                            if hasattr(base_elem, 'string'):
                                base_elem.string = ''
                            else:
                                for child in list(base_elem.children):
                                    if hasattr(child, 'get_text'):
                                        try:
                                            if child.get_text(strip=True):
                                                child.decompose()
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        stats['diffElements'] += 1
                        if len(texts) >= 2:
                            stats['differences'].append(f"テキストが異なります ({base_selector}): {texts[0][:30]}... vs {texts[1][:30]}...")
                    elif diff_handling == 'comment':
                        # 差異をコメントとして追加
                        try:
                            comment_text = f"<!-- 差異: {', '.join(list(set(texts))[:3])} -->"
                            if hasattr(base_elem, 'insert'):
                                base_elem.insert(0, BeautifulSoup(comment_text, 'html.parser'))
                        except Exception:
                            pass
        
        return base_elem
    
    # body要素を統合
    if base_soup.body:
        merge_element(base_soup.body, parsed_files[1:])
    
    # head要素も統合（スタイルなど）
    if options.get('styles', True) and base_soup.head:
        merge_element(base_soup.head, parsed_files[1:])
    
    # 統計を更新
    stats['mergedElements'] = stats['commonElements']
    
    # 統合されたHTMLを生成
    merged_html = str(base_soup)
    
    return merged_html, stats


def main():
    """メイン関数"""
    # WindowsでUTF-8を有効化
    if sys.platform == 'win32':
        try:
            os.system('chcp 65001 >nul 2>&1')
            # 標準出力のエンコーディングをUTF-8に設定
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    parser = argparse.ArgumentParser(
        description='Webブラウザ上でHTMLファイルを編集するツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python web_html_editor.py
  python web_html_editor.py suikankyo.html
  python web_html_editor.py suikankyo.html --port 5000
  python web_html_editor.py suikankyo.html --host 0.0.0.0 --port 8080
        """
    )
    parser.add_argument(
        'html_file',
        type=str,
        nargs='?',
        default=None,
        help='編集するHTMLファイルのパス（オプション: ブラウザからアップロードも可能）'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='ホストアドレス (デフォルト: 127.0.0.1)'
    )
    # RailwayやHerokuなどのクラウド環境では環境変数PORTを使用
    port_env = os.environ.get('PORT')
    default_port = int(port_env) if port_env else 5000
    print(f"環境変数PORT: {port_env}, デフォルトポート: {default_port}", flush=True)
    parser.add_argument(
        '--port',
        type=int,
        default=default_port,
        help=f'ポート番号 (デフォルト: {default_port}, 環境変数PORTが設定されている場合はそれを使用)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグモードを有効化'
    )
    
    args = parser.parse_args()
    
    global html_file_path, html_editor
    
    # HTMLファイルが指定されている場合は読み込む
    if args.html_file:
        html_file_path = Path(args.html_file)
        if not html_file_path.exists():
            print(f"エラー: ファイル '{html_file_path}' が見つかりません。")
            sys.exit(1)
        
        try:
            print(f"HTMLファイルを読み込み中: {html_file_path}")
            html_editor = HTMLEditor(str(html_file_path))
            print("読み込み完了！")
        except Exception as e:
            print(f"エラー: ファイルの読み込みに失敗しました: {e}")
            sys.exit(1)
    else:
        print("ファイルが指定されていません。ブラウザからファイルをアップロードしてください。")
    
    try:
        # Flaskアプリケーションのログレベルを設定（Railway環境でのデバッグ用）
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        app.logger.setLevel(logging.INFO)
        app.logger.info("FlaskアプリケーションのログレベルをINFOに設定しました")
        print("FlaskアプリケーションのログレベルをINFOに設定しました", flush=True)
        
        # 登録されているルートを確認
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(f"{rule.rule} -> {rule.endpoint} ({', '.join(rule.methods)})")
        routes_msg = "登録されているルート:\n" + "\n".join(routes)
        app.logger.info(routes_msg)
        print(routes_msg, flush=True)
        
        # before_requestハンドラーが登録されているか確認
        before_request_handlers = len(app.before_request_funcs.get(None, []))
        msg = f"before_requestハンドラーの数: {before_request_handlers}"
        app.logger.info(msg)
        print(msg, flush=True)
        
        # フロントエンドビルドディレクトリの確認
        print(f"\n{'='*60}")
        print(f"フロントエンドビルドディレクトリの確認:")
        print(f"  現在の作業ディレクトリ: {os.getcwd()}")
        print(f"  スクリプトのディレクトリ: {Path(__file__).parent}")
        print(f"  FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR}")
        print(f"  存在確認: {FRONTEND_DIST_DIR.exists()}")
        
        # _find_index_html()でindex.htmlを検索
        index_path = _find_index_html()
        if index_path:
            print(f"  ✓ index.html が見つかりました: {index_path}")
        else:
            print(f"  ✗ index.html が見つかりませんでした")
            print(f"    試したパス:")
            print(f"      - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'index.html'}")
            for dist_dir in _ALTERNATIVE_PATHS:
                print(f"      - {dist_dir / 'index.html'}")
        
        # _find_assets_dir()でassetsディレクトリを検索
        assets_dir = _find_assets_dir()
        if assets_dir:
            print(f"  ✓ assetsディレクトリが見つかりました: {assets_dir}")
        else:
            print(f"  ✗ assetsディレクトリが見つかりませんでした")
        
        if FRONTEND_DIST_DIR.exists():
            try:
                contents = list(FRONTEND_DIST_DIR.iterdir())
                print(f"  FRONTEND_DIST_DIRの内容: {[str(c.name) for c in contents]}")
            except Exception as e:
                print(f"  ディレクトリの内容を取得できませんでした: {e}")
        print(f"{'='*60}")
        
        url = f"http://{args.host}:{args.port}"
        print(f"\n{'='*60}")
        print(f"Webエディタを起動しました！")
        print(f"{'='*60}")
        print(f"ブラウザで以下のURLを開いてください:")
        print(f"  {url}")
        if not args.html_file:
            try:
                print(f"\n💡 ヒント: 「ファイルをアップロード」ボタンからHTMLファイルをアップロードできます")
            except UnicodeEncodeError:
                print(f"\nヒント: 「ファイルをアップロード」ボタンからHTMLファイルをアップロードできます")
        print(f"\n終了するには Ctrl+C を押してください")
        print(f"{'='*60}\n")
        
        # RailwayやHerokuなどのクラウド環境では0.0.0.0でリッスン
        host = args.host
        railway_env = os.environ.get('RAILWAY_ENVIRONMENT')
        dyno = os.environ.get('DYNO')
        port_env = os.environ.get('PORT')
        print(f"環境変数確認: RAILWAY_ENVIRONMENT={railway_env}, DYNO={dyno}, PORT={port_env}", flush=True)
        if railway_env or dyno or port_env:
            host = '0.0.0.0'
            print(f"Railway環境を検出しました。host={host}, port={args.port}", flush=True)
        
        app.run(host=host, port=args.port, debug=args.debug)
    
    except KeyboardInterrupt:
        print("\n\nプログラムを終了します。")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ==================== 大学データ管理API ====================

@app.route('/api/universities', methods=['GET'])
def get_universities():
    """大学一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM universities ORDER BY code')
        universities = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'universities': universities})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/universities', methods=['POST'])
def create_university():
    """大学を登録"""
    try:
        data = request.json
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        
        if not code or not name:
            return jsonify({'success': False, 'error': '大学コードと名前は必須です'}), 400
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO universities (code, name) 
            VALUES (?, ?)
        ''', (code, name))
        
        university_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'id': university_id})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'この大学コードは既に登録されています'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/page-titles', methods=['GET'])
def get_page_titles():
    """ページタイトル一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM page_titles ORDER BY display_order, title')
        titles = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'titles': titles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/pages', methods=['GET'])
def get_university_pages(university_id):
    """大学のページデータ一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT upd.*, pt.title as page_title
            FROM university_page_data upd
            JOIN page_titles pt ON upd.page_title_id = pt.id
            WHERE upd.university_id = ?
            ORDER BY pt.display_order, pt.title
        ''', (university_id,))
        
        pages = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'pages': pages})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/page/<int:page_title_id>', methods=['GET', 'POST', 'PUT'])
def manage_university_page(university_id, page_title_id):
    """大学のページデータを取得・作成・更新"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if request.method == 'GET':
            cursor.execute('''
                SELECT upd.*, pt.title as page_title
                FROM university_page_data upd
                JOIN page_titles pt ON upd.page_title_id = pt.id
                WHERE upd.university_id = ? AND upd.page_title_id = ?
            ''', (university_id, page_title_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return jsonify({'success': True, 'page': dict(row)})
            else:
                return jsonify({'success': False, 'error': 'ページデータが見つかりません'}), 404
        
        elif request.method in ['POST', 'PUT']:
            data = request.json
            content = data.get('content', '')
            metadata = json.dumps(data.get('metadata', {}), ensure_ascii=False)
            
            cursor.execute('''
                INSERT OR REPLACE INTO university_page_data 
                (university_id, page_title_id, content, metadata, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (university_id, page_title_id, content, metadata))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/config', methods=['GET', 'POST', 'PUT'])
def manage_university_config(university_id):
    """大学のJSON設定ファイルを管理"""
    try:
        config_file = UNIVERSITY_CONFIG_DIR / f'university_{university_id}.json'
        
        if request.method == 'GET':
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return jsonify({'success': True, 'config': config})
            else:
                # デフォルト設定を返す
                return jsonify({'success': True, 'config': {
                    'layout': {},
                    'display_order': [],
                    'items': {}  # 各項目の属性を管理
                }})
        
        elif request.method in ['POST', 'PUT']:
            data = request.json
            config = data.get('config', {})
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-university-page', methods=['POST'])
def generate_university_page():
    """共通テンプレートと大学データを統合してページを生成"""
    try:
        data = request.json
        university_id = data.get('university_id')
        page_title_id = data.get('page_title_id')
        template_html = data.get('template', '')
        
        if not university_id or not page_title_id or not template_html:
            return jsonify({'success': False, 'error': '必要なパラメータが不足しています'}), 400
        
        # 大学データを取得
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT upd.content, upd.metadata, pt.title as page_title
            FROM university_page_data upd
            JOIN page_titles pt ON upd.page_title_id = pt.id
            WHERE upd.university_id = ? AND upd.page_title_id = ?
        ''', (university_id, page_title_id))
        
        page_data = cursor.fetchone()
        
        # 大学設定を取得
        config_file = UNIVERSITY_CONFIG_DIR / f'university_{university_id}.json'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {'layout': {}, 'display_order': [], 'items': {}}
        
        conn.close()
        
        # テンプレートを解析
        soup = BeautifulSoup(template_html, 'html.parser')
        
        # 大学データをテンプレートに埋め込む
        if page_data:
            content = page_data['content'] or ''
            metadata = json.loads(page_data['metadata'] or '{}')
            
            # コンテンツエリアを探して置き換え
            content_area = soup.find(id='content') or soup.find(class_='content') or soup.find('main')
            if content_area:
                content_area.clear()
                content_soup = BeautifulSoup(content, 'html.parser')
                content_area.append(content_soup)
        
        # レイアウト設定を適用
        layout = config.get('layout', {})
        display_order = config.get('display_order', [])
        items_config = config.get('items', {})  # 各項目の属性設定
        
        # 各項目の属性を適用
        if items_config:
            for item_id, item_attrs in items_config.items():
                # ID、クラス、data属性などで要素を検索
                element = None
                
                # IDで検索
                if item_attrs.get('id'):
                    element = soup.find(id=item_attrs['id'])
                
                # クラスで検索
                if not element and item_attrs.get('class'):
                    classes = item_attrs['class']
                    if isinstance(classes, str):
                        classes = [classes]
                    element = soup.find(class_=classes[0]) if classes else None
                
                # data属性で検索
                if not element and item_attrs.get('data_attr'):
                    data_attr = item_attrs['data_attr']
                    element = soup.find(attrs={data_attr: item_id})
                
                if element:
                    # 表示/非表示
                    if item_attrs.get('visible') is False:
                        element['style'] = (element.get('style', '') + '; display: none;').strip('; ')
                    elif item_attrs.get('visible') is True:
                        # 表示する場合は既存のdisplay:noneを削除
                        style = element.get('style', '')
                        style = style.replace('display: none;', '').replace('display:none;', '')
                        element['style'] = style.strip('; ')
                    
                    # 位置（order）
                    if 'order' in item_attrs:
                        element['style'] = (element.get('style', '') + f'; order: {item_attrs["order"]};').strip('; ')
                    
                    # CSSスタイル
                    if item_attrs.get('styles'):
                        existing_style = element.get('style', '')
                        for prop, value in item_attrs['styles'].items():
                            # CSSプロパティ名をケバブケースに変換
                            css_prop = prop.replace('_', '-')
                            existing_style = existing_style.replace(f'{css_prop}:', '').strip('; ')
                            existing_style = (existing_style + f'; {css_prop}: {value};').strip('; ')
                        element['style'] = existing_style
                    
                    # クラスの追加/削除
                    if item_attrs.get('add_classes'):
                        add_classes = item_attrs['add_classes']
                        if isinstance(add_classes, str):
                            add_classes = [add_classes]
                        existing_classes = element.get('class', [])
                        if isinstance(existing_classes, str):
                            existing_classes = [existing_classes]
                        element['class'] = list(set(existing_classes + add_classes))
                    
                    if item_attrs.get('remove_classes'):
                        remove_classes = item_attrs['remove_classes']
                        if isinstance(remove_classes, str):
                            remove_classes = [remove_classes]
                        existing_classes = element.get('class', [])
                        if isinstance(existing_classes, str):
                            existing_classes = [existing_classes]
                        element['class'] = [cls for cls in existing_classes if cls not in remove_classes]
                    
                    # 属性の追加/変更
                    if item_attrs.get('attributes'):
                        for attr_name, attr_value in item_attrs['attributes'].items():
                            element[attr_name] = attr_value
                    
                    # テキストコンテンツの変更
                    if 'text_content' in item_attrs:
                        element.string = item_attrs['text_content']
                    
                    # HTMLコンテンツの変更
                    if 'html_content' in item_attrs:
                        element.clear()
                        html_soup = BeautifulSoup(item_attrs['html_content'], 'html.parser')
                        element.append(html_soup)
        
        # 表示順序に従って要素を並び替え
        if display_order:
            body = soup.find('body')
            if body:
                sections = {}
                for elem in body.find_all(['section', 'div'], class_=True):
                    classes = elem.get('class', [])
                    for cls in classes:
                        if cls in display_order:
                            sections[cls] = elem
                            break
                
                # 順序に従って再配置
                for cls in display_order:
                    if cls in sections:
                        body.append(sections[cls])
        
        generated_html = str(soup)
        
        return jsonify({
            'success': True,
            'html': generated_html,
            'page_title': page_data['title'] if page_data else None
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== YAML設定ファイルベースのページ生成 ====================

def load_yaml_config():
    """YAML設定ファイルを読み込む"""
    config_path = Path(__file__).parent / 'university_pages_config.yml'
    if not config_path.exists():
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_form_field_html(field_config):
    """フォームフィールドの設定からHTMLを生成"""
    field_type = field_config.get('type', 'text')
    name = field_config.get('name', '')
    label = field_config.get('label', '')
    required = field_config.get('required', False)
    
    html_parts = []
    
    # ラベル
    if label and field_type not in ['section', 'navigation']:
        required_mark = ' <span style="color: red;">*</span>' if required else ''
        html_parts.append(f'<label for="{name}" style="display: block; margin-bottom: 5px; font-weight: 600;">{label}{required_mark}</label>')
    
    # フィールド本体
    if field_type == 'text':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="text" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'textarea':
        required_attr = 'required' if required else ''
        html_parts.append(f'<textarea id="{name}" name="{name}" class="form-control" {required_attr} rows="4" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;"></textarea>')
    
    elif field_type == 'date':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="date" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'tel':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="tel" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'email':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="email" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'number':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="number" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'select':
        options = field_config.get('options', [])
        required_attr = 'required' if required else ''
        options_html = ''.join([f'<option value="{opt}">{opt}</option>' for opt in options])
        html_parts.append(f'<select id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">{options_html}</select>')
    
    elif field_type == 'checkbox':
        checked_attr = 'checked' if field_config.get('checked', False) else ''
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="checkbox" id="{name}" name="{name}" {checked_attr} {required_attr} style="margin-right: 5px; margin-bottom: 15px;">')
    
    elif field_type == 'radio':
        options = field_config.get('options', [])
        required_attr = 'required' if required else ''
        radio_html = []
        for opt in options:
            radio_id = f"{name}_{opt}"
            radio_html.append(f'<div style="margin-bottom: 10px;"><input type="radio" id="{radio_id}" name="{name}" value="{opt}" {required_attr} style="margin-right: 5px;"><label for="{radio_id}">{opt}</label></div>')
        html_parts.append(''.join(radio_html))
    
    elif field_type == 'file':
        accept = field_config.get('accept', '')
        multiple = 'multiple' if field_config.get('multiple', False) else ''
        required_attr = 'required' if required else ''
        accept_attr = f'accept="{accept}"' if accept else ''
        html_parts.append(f'<input type="file" id="{name}" name="{name}" class="form-control" {required_attr} {accept_attr} {multiple} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'section':
        html_parts.append(f'<h2 style="margin-top: 30px; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #667eea;">{label}</h2>')
    
    elif field_type == 'navigation':
        html_parts.append(f'<nav style="margin-bottom: 20px;"><ul style="list-style: none; padding: 0;">{label}</ul></nav>')
    
    return '\n'.join(html_parts)


def generate_page_html(page_config, university_config=None, generation_settings=None):
    """ページ設定からHTMLを生成"""
    page_title = page_config.get('title', '')
    page_id = page_config.get('id', '')
    description = page_config.get('description', '')
    form_fields = page_config.get('form_fields', [])
    
    # 大学のカスタマイズ設定を取得
    custom_fields = []
    if university_config:
        for custom_page in university_config.get('custom_pages', []):
            if custom_page.get('page_title_id') == page_id:
                custom_fields = custom_page.get('custom_fields', [])
                break
    
    # HTMLの生成
    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="ja">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{page_title}</title>')
    
    # CSSフレームワークの設定
    css_framework = generation_settings.get('template', {}).get('css_framework', 'bootstrap') if generation_settings else 'bootstrap'
    if css_framework == 'bootstrap':
        html_parts.append('    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">')
    html_parts.append('    <style>')
    html_parts.append('        body { font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif; padding: 20px; background-color: #f5f5f5; }')
    html_parts.append('        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
    html_parts.append('        .form-control { margin-bottom: 15px; }')
    html_parts.append('        .btn-submit { background-color: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }')
    html_parts.append('        .btn-submit:hover { background-color: #5568d3; }')
    html_parts.append('        .description { color: #666; margin-bottom: 20px; }')
    html_parts.append('    </style>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="container">')
    html_parts.append(f'        <h1>{page_title}</h1>')
    if description:
        html_parts.append(f'        <p class="description">{description}</p>')
    
    html_parts.append('        <form id="admissionForm" method="POST" action="#" enctype="multipart/form-data">')
    
    # カスタムフィールド（before位置）を挿入
    for custom_field in custom_fields:
        if custom_field.get('position') == 'before':
            target = custom_field.get('target_field', '')
            # ターゲットフィールドの前に挿入
            html_parts.append(generate_form_field_html(custom_field))
    
    # 通常のフォームフィールド
    for field in form_fields:
        html_parts.append(generate_form_field_html(field))
    
    # カスタムフィールド（after位置）を挿入
    for custom_field in custom_fields:
        if custom_field.get('position') != 'before':
            html_parts.append(generate_form_field_html(custom_field))
    
    html_parts.append('            <div style="margin-top: 30px; text-align: center;">')
    html_parts.append('                <button type="submit" class="btn-submit">送信</button>')
    html_parts.append('                <button type="button" onclick="history.back()" style="margin-left: 10px; padding: 12px 30px; background-color: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">戻る</button>')
    html_parts.append('            </div>')
    html_parts.append('        </form>')
    html_parts.append('    </div>')
    
    # JavaScript
    html_parts.append('    <script>')
    html_parts.append('        document.getElementById("admissionForm").addEventListener("submit", function(e) {')
    html_parts.append('            e.preventDefault();')
    html_parts.append('            // フォーム送信処理をここに実装')
    html_parts.append('            alert("送信機能は実装されていません");')
    html_parts.append('        });')
    html_parts.append('    </script>')
    html_parts.append('</body>')
    html_parts.append('</html>')
    
    return '\n'.join(html_parts)


@app.route('/api/generate-pages-from-yaml', methods=['POST'])
def generate_pages_from_yaml():
    """YAML設定ファイルを基に指定した大学または全大学の入学手続きWEBページを生成"""
    try:
        data = request.json
        university_codes = data.get('university_codes', [])  # 空の場合は全大学
        output_directory = data.get('output_directory', '')
        
        # YAML設定ファイルを読み込む
        yaml_config = load_yaml_config()
        if not yaml_config:
            return jsonify({'success': False, 'error': 'YAML設定ファイルが見つかりません'}), 404
        
        default_page_titles = yaml_config.get('default_page_titles', [])
        universities_config = yaml_config.get('universities', [])
        generation_settings = yaml_config.get('generation_settings', {})
        page_mappings = yaml_config.get('page_mappings', [])
        
        # 出力ディレクトリの設定
        if output_directory:
            output_dir = Path(output_directory)
        else:
            output_dir = UPLOAD_DIR / 'generated_university_pages'
        
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # データベースから大学情報を取得
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 対象大学を決定
        if university_codes:
            # 指定された大学コードの大学を取得
            placeholders = ','.join(['?' for _ in university_codes])
            cursor.execute(f'SELECT * FROM universities WHERE code IN ({placeholders})', university_codes)
        else:
            # 全大学を取得
            cursor.execute('SELECT * FROM universities ORDER BY code')
        
        universities = cursor.fetchall()
        conn.close()
        
        if not universities:
            return jsonify({'success': False, 'error': '対象となる大学が見つかりませんでした'}), 404
        
        generated_files = []
        total_pages = 0
        success_count = 0
        failed_count = 0
        
        # 各大学に対してページを生成
        for university in universities:
            university_code = university['code']
            university_name = university['name']
            university_id = university['id']
            
            # 大学の設定を取得
            university_config = None
            for univ_config in universities_config:
                if univ_config.get('code') == university_code:
                    university_config = univ_config
                    break
            
            # 大学ごとの出力ディレクトリを作成
            univ_output_dir = output_dir / f"{university_code}_{university_name}"
            univ_output_dir.mkdir(exist_ok=True, parents=True)
            
            # 各ページタイトルに対してページを生成
            for page_config in default_page_titles:
                try:
                    page_id = page_config.get('id')
                    page_title = page_config.get('title', '')
                    
                    # ページマッピングからファイル名を取得
                    file_name = f"page_{page_id}_{page_title}.html"
                    route = f"/page-{page_id}"
                    for mapping in page_mappings:
                        if mapping.get('page_title_id') == page_id:
                            file_name = mapping.get('file_name', file_name)
                            route = mapping.get('route', route)
                            break
                    
                    # HTMLを生成
                    html_content = generate_page_html(
                        page_config,
                        university_config,
                        generation_settings
                    )
                    
                    # ファイルに保存
                    output_file = univ_output_dir / file_name
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    generated_files.append({
                        'university_code': university_code,
                        'university_name': university_name,
                        'page_id': page_id,
                        'page_title': page_title,
                        'file_name': file_name,
                        'file_path': str(output_file)
                    })
                    
                    total_pages += 1
                    success_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Error generating page {page_id} for {university_code}: {str(e)}")
                    continue
        
        return jsonify({
            'success': True,
            'message': f'{len(universities)}大学、合計{total_pages}ページを生成しました',
            'universities_count': len(universities),
            'total_pages': total_pages,
            'success_count': success_count,
            'failed_count': failed_count,
            'output_directory': str(output_dir),
            'generated_files': generated_files
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-pages-from-yaml-download', methods=['POST'])
def generate_pages_from_yaml_download():
    """YAML設定ファイルを基に生成したページをZIPファイルでダウンロード"""
    try:
        data = request.json
        output_directory = data.get('output_directory', '')
        
        if not output_directory:
            output_directory = str(UPLOAD_DIR / 'generated_university_pages')
        
        output_dir = Path(output_directory)
        if not output_dir.exists():
            return jsonify({'success': False, 'error': '出力ディレクトリが見つかりません'}), 404
        
        # ZIPファイルを作成
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in output_dir.rglob('*.html'):
                arcname = file_path.relative_to(output_dir)
                zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'university_pages_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/<path:path>')
def catch_all(path):
    """SPAルーティング用のキャッチオールルート - APIルート以外はすべてindex.htmlを返す"""
    # APIルートの場合は404を返す
    if path.startswith('api/') or path.startswith('save') or path.startswith('upload') or \
       path.startswith('files') or path.startswith('search') or path.startswith('structure') or \
       path.startswith('validate') or path.startswith('download') or path.startswith('favicon.ico') or \
       path.startswith('assets/'):
        return jsonify({'error': 'Not found'}), 404
    
    # それ以外はReactアプリを返す
    return _serve_index_html()


if __name__ == "__main__":
    main()

