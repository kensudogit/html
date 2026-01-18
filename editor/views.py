"""
Views for editor app.
"""
import os
import sys
import traceback
import json
import sqlite3
import secrets
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from werkzeug.utils import secure_filename
import logging

from html_editor import HTMLEditor
from bs4 import BeautifulSoup
import yaml

logger = logging.getLogger(__name__)

# セッション別のファイル管理用ディクショナリ（Djangoセッションと連携）
session_files = {}


def get_session_file_info(request):
    """
    セッションからファイル情報を取得
    
    Returns:
        dict: セッションに対応するファイル情報
            - 'html_editor': HTMLEditorオブジェクト（未選択時はNone）
            - 'html_file_path': ファイルパス（未選択時はNone）
    """
    # セッションIDを取得（存在しない場合は新規生成）
    session_id = request.session.get('session_id')
    if not session_id:
        # 新規セッションの場合、16バイトのランダムな16進数文字列を生成
        session_id = secrets.token_hex(16)
        request.session['session_id'] = session_id
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


def set_session_file_info(request, html_editor_obj, file_path):
    """
    セッションにファイル情報を保存
    
    Args:
        request: Django requestオブジェクト
        html_editor_obj: HTMLEditorオブジェクト
        file_path: ファイルパス（Pathオブジェクトまたは文字列）
    """
    session_id = request.session.get('session_id')
    if not session_id:
        session_id = secrets.token_hex(16)
        request.session['session_id'] = session_id
    
    # ファイルパスを文字列に変換
    if isinstance(file_path, Path):
        file_path_str = str(file_path)
    else:
        file_path_str = file_path
    
    session_files[session_id] = {
        'html_editor': html_editor_obj,
        'html_file_path': file_path_str
    }

# アップロードディレクトリ
UPLOAD_DIR = Path(settings.MEDIA_ROOT)
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# フロントエンドのビルドディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'
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


def _find_index_html():
    """index.htmlを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    index_path = FRONTEND_DIST_DIR / 'index.html'
    if index_path.exists():
        logger.info(f"index.htmlを見つけました（FRONTEND_DIST_DIR）: {index_path}")
        return index_path
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        index_path = dist_dir / 'index.html'
        if index_path.exists():
            logger.info(f"index.htmlを見つけました（代替パス）: {index_path}")
            return index_path
    
    logger.error(f"index.htmlが見つかりません。試したパス:")
    logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'index.html'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        logger.error(f"  - {dist_dir / 'index.html'}")
    return None


def _find_assets_dir():
    """assetsディレクトリを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    assets_dir = FRONTEND_DIST_DIR / 'assets'
    if assets_dir.exists() and assets_dir.is_dir():
        logger.info(f"assetsディレクトリを見つけました（FRONTEND_DIST_DIR）: {assets_dir}")
        return assets_dir
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        assets_dir = dist_dir / 'assets'
        if assets_dir.exists() and assets_dir.is_dir():
            logger.info(f"assetsディレクトリを見つけました（代替パス）: {assets_dir}")
            return assets_dir
    
    logger.error(f"assetsディレクトリが見つかりません。試したパス:")
    logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'assets'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        logger.error(f"  - {dist_dir / 'assets'}")
    return None


def _load_template(template_name, **kwargs):
    """テンプレートファイルを読み込んで変数を置換"""
    try:
        template_path = BASE_DIR / 'templates' / template_name
        if not template_path.exists():
            logger.error(f"テンプレートファイルが見つかりません: {template_path}")
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 変数を置換
        for key, value in kwargs.items():
            content = content.replace(f'{{{key}}}', str(value))
        
        return content
    except Exception as e:
        logger.error(f"テンプレート読み込みエラー ({template_name}): {e}")
        return None


def _serve_index_html():
    """index.htmlを返す共通関数"""
    try:
        msg = f"=== index.html配信開始 ===\n現在の作業ディレクトリ: {os.getcwd()}\nスクリプトのディレクトリ: {BASE_DIR}\nFRONTEND_DIST_DIR: {FRONTEND_DIST_DIR}\nFRONTEND_DIST_DIR 存在確認: {FRONTEND_DIST_DIR.exists()}"
        logger.info(msg)
        print(msg, flush=True)
        
        index_path = _find_index_html()
        
        if index_path:
            msg = f"index.htmlを配信します: {index_path}"
            logger.info(msg)
            print(msg, flush=True)
            return FileResponse(open(index_path, 'rb'), content_type='text/html')
        else:
            logger.error(f"Reactビルドファイルが見つかりません。試したパス: {[str(p / 'index.html') for p in _ALTERNATIVE_PATHS]}")
            tried_paths_html = ''.join([f'<li>{str(p / "index.html")}</li>' for p in _ALTERNATIVE_PATHS])
            error_html = _load_template(
                'build_not_found.html',
                work_dir=os.getcwd(),
                script_dir=BASE_DIR,
                tried_paths=tried_paths_html
            )
            if error_html:
                return HttpResponse(error_html, status=500, content_type='text/html')
            else:
                return HttpResponse(f"""
                <!DOCTYPE html>
                <html lang="ja">
                <head>
                    <meta charset="UTF-8">
                    <title>ビルドファイルが見つかりません</title>
                    <style>
                        body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                        .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h1>ビルドファイルが見つかりません</h1>
                        <p>frontend/dist/index.html が存在しません。ビルドを実行してください。</p>
                    </div>
                </body>
                </html>
                """, status=500, content_type='text/html')
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"index.html配信エラー: {error_details}")
        error_html = _load_template(
            'error_page.html',
            error_message=str(e),
            error_details=error_details
        )
        if error_html:
            return HttpResponse(error_html, status=500, content_type='text/html')
        else:
            return HttpResponse(f"""
            <!DOCTYPE html>
            <html lang="ja">
            <head>
                <meta charset="UTF-8">
                <title>エラー</title>
                <style>
                    body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                    .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>エラーが発生しました</h1>
                    <p><strong>エラーメッセージ:</strong> {str(e)}</p>
                </div>
            </body>
            </html>
            """, status=500, content_type='text/html')


def index(request):
    """メインページ - Reactアプリケーションを配信"""
    msg = "=== ルートパス (/) へのリクエスト ==="
    logger.info(msg)
    print(msg, flush=True)
    try:
        return _serve_index_html()
    except Exception as e:
        error_msg = f"index() でエラーが発生: {e}"
        logger.error(error_msg)
        print(error_msg, flush=True)
        tb = traceback.format_exc()
        logger.error(tb)
        print(tb, flush=True)
        raise


def serve_assets(request, filename):
    """静的アセット（JS、CSSなど）を配信"""
    try:
        assets_dir = _find_assets_dir()
        if assets_dir:
            file_path = assets_dir / filename
            if file_path.exists():
                return FileResponse(open(file_path, 'rb'))
        return HttpResponse('Asset not found', status=404)
    except Exception as e:
        logger.error(f"静的アセット配信エラー: {e}, filename: {filename}")
        return HttpResponse('Asset not found', status=404)


def favicon(request):
    """faviconを返す（404エラーを防ぐため）"""
    try:
        for dist_dir in _ALTERNATIVE_PATHS:
            favicon_path = dist_dir / 'favicon.ico'
            if favicon_path.exists():
                return FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon')
        return HttpResponse(b'', content_type='image/x-icon')
    except Exception:
        return HttpResponse(b'', content_type='image/x-icon')


@csrf_exempt
@require_http_methods(["POST"])
def save(request):
    """ファイルを保存"""
    try:
        file_info = get_session_file_info(request)
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return JsonResponse({'success': False, 'error': 'ファイルが選択されていません'}, status=400)
        
        data = json.loads(request.body)
        content = data.get('content', '')
        
        # ファイルに保存
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(request, html_editor, html_file_path)
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"save error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def content(request):
    """HTMLコンテンツを取得"""
    try:
        file_info = get_session_file_info(request)
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None or not Path(html_file_path).exists():
            return JsonResponse({'success': False, 'error': 'ファイルが選択されていません'}, status=400)
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return JsonResponse({'success': True, 'content': content})
    except Exception as e:
        logger.error(f"content error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def reload(request):
    """ファイルを再読み込み"""
    try:
        file_info = get_session_file_info(request)
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return JsonResponse({'success': False, 'error': 'ファイルが選択されていません'}, status=400)
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(request, html_editor, html_file_path)
        
        return JsonResponse({'success': True, 'content': content})
    except Exception as e:
        logger.error(f"reload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def structure(request):
    """構造情報を取得"""
    try:
        file_info = get_session_file_info(request)
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return JsonResponse({'success': False, 'error': 'HTMLエディタが初期化されていません'}, status=500)
        
        info = html_editor.get_structure_info()
        return JsonResponse({'success': True, 'info': info})
    except Exception as e:
        logger.error(f"structure error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def search(request):
    """要素を検索"""
    try:
        file_info = get_session_file_info(request)
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return JsonResponse({'success': False, 'error': 'HTMLエディタが初期化されていません'}, status=500)
        
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        
        if not query:
            return JsonResponse({'success': False, 'error': '検索文字列が空です'})
        
        results = []
        
        # IDで検索
        element = html_editor.find_by_id(query)
        if element:
            results.append({
                'tag': element.name,
                'id': element.get('id', ''),
                'class': ' '.join(element.get('class', [])),
                'type': 'id',
                'text': element.get_text(strip=True)[:50]
            })
        
        # クラスで検索
        elements = html_editor.find_by_class(query)
        for elem in elements[:10]:
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'class',
                'text': elem.get_text(strip=True)[:50]
            })
        
        # タグで検索
        elements = html_editor.find_by_tag(query)
        for elem in elements[:10]:
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'tag',
                'text': elem.get_text(strip=True)[:50]
            })
        
        # テキスト内容で検索（部分一致）
        try:
            text_elements = html_editor.find_by_text(query, exact=False)
            for text_node in text_elements[:10]:
                parent = text_node.parent if hasattr(text_node, 'parent') else None
                if parent:
                    results.append({
                        'tag': parent.name,
                        'id': parent.get('id', ''),
                        'class': ' '.join(parent.get('class', [])),
                        'type': 'text',
                        'text': text_node.strip()[:50] if isinstance(text_node, str) else str(text_node)[:50]
                    })
        except Exception:
            pass
        
        return JsonResponse({'success': True, 'results': results})
    except Exception as e:
        logger.error(f"search error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload(request):
    """ファイルをアップロード"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'ファイルが選択されていません'}, status=400)
        
        file = request.FILES['file']
        if file.name == '':
            return JsonResponse({'success': False, 'error': 'ファイルが選択されていません'}, status=400)
        
        # ファイル名を安全にする
        filename = secure_filename(file.name)
        
        # HTMLファイルかチェック
        if not (filename.lower().endswith('.html') or filename.lower().endswith('.htm')):
            return JsonResponse({'success': False, 'error': 'HTMLファイルのみアップロード可能です'}, status=400)
        
        # アップロードフォルダに保存
        file_path = UPLOAD_DIR / filename
        with open(file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        
        # セッションにファイル情報を保存
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(request, html_editor, file_path)
        
        return JsonResponse({'success': True, 'filename': filename})
    except Exception as e:
        logger.error(f"upload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def files(request):
    """ファイル一覧を取得"""
    try:
        files_list = []
        for file_path in UPLOAD_DIR.glob('*.html'):
            if file_path.is_file():
                files_list.append({
                    'name': file_path.name,
                    'size': file_path.stat().st_size
                })
        
        return JsonResponse({'success': True, 'files': files_list})
    except Exception as e:
        logger.error(f"files error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def load_file(request, filename):
    """ファイルを読み込み"""
    try:
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return JsonResponse({'success': False, 'error': 'ファイルが見つかりません'}, status=404)
        
        # セッションにファイル情報を保存
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(request, html_editor, file_path)
        
        return JsonResponse({'success': True, 'filename': filename})
    except Exception as e:
        logger.error(f"load_file error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_file(request, filename):
    """ファイルを削除"""
    try:
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return JsonResponse({'success': False, 'error': 'ファイルが見つかりません'}, status=404)
        
        file_path.unlink()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"delete_file error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# スタブ関数（後で実装）
@csrf_exempt
@require_http_methods(["POST"])
def validate(request):
    """HTMLを検証"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def diff_analysis(request):
    """差分分析"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def gcd_template(request):
    """GCDテンプレート"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def template_merge(request):
    """テンプレートマージ"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def generate_university_pages(request):
    """大学ページ生成"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def download_university_pages(request):
    """大学ページダウンロード"""
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


# APIエンドポイント（スタブ）
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_list_directory_files(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@require_http_methods(["GET"])
def api_config(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_check_directory(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_load_comparison_files(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@require_http_methods(["GET"])
def api_load_file_content(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_compare_screens(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def api_export_comparison_report(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_universities(request):
    """大学一覧を取得または作成"""
    if request.method == 'GET':
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM universities ORDER BY code')
            universities = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return JsonResponse({'success': True, 'universities': universities})
        except Exception as e:
            logger.error(f"api_universities GET error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    else:  # POST
        try:
            data = json.loads(request.body)
            code = data.get('code', '').strip()
            name = data.get('name', '').strip()
            
            if not code or not name:
                return JsonResponse({'success': False, 'error': '大学コードと名前は必須です'}, status=400)
            
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO universities (code, name) 
                VALUES (?, ?)
            ''', (code, name))
            
            university_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return JsonResponse({'success': True, 'id': university_id})
        except sqlite3.IntegrityError:
            return JsonResponse({'success': False, 'error': 'この大学コードは既に登録されています'}, status=400)
        except Exception as e:
            logger.error(f"api_universities POST error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_page_titles(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@require_http_methods(["GET"])
def api_university_pages(request, university_id):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def api_university_page_detail(request, university_id, page_title_id):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def api_university_config(request, university_id):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_university_page(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_pages_from_yaml(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_pages_from_yaml_download(request):
    return JsonResponse({'success': False, 'error': 'Not implemented yet'}, status=501)
