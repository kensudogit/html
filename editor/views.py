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

import sys
import importlib.util
from pathlib import Path
# html_editor.pyモジュールをインポート（Djangoプロジェクト名と衝突を避けるため）
html_editor_file = Path(__file__).resolve().parent.parent / 'html_editor.py'
spec = importlib.util.spec_from_file_location("html_editor_module", html_editor_file)
html_editor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(html_editor_module)
HTMLEditor = html_editor_module.HTMLEditor
from bs4 import BeautifulSoup
import yaml
from datetime import datetime

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


def serve_logo(request):
    """ロゴ画像を返す"""
    try:
        for dist_dir in _ALTERNATIVE_PATHS:
            logo_path = dist_dir / 'logo.png'
            if logo_path.exists():
                return FileResponse(open(logo_path, 'rb'), content_type='image/png')
        return HttpResponse('Logo not found', status=404)
    except Exception as e:
        logger.error(f"ロゴ画像配信エラー: {e}")
        return HttpResponse('Logo not found', status=404)


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
    """要素を検索（HTML）またはExcelファイルを検索"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        search_type = data.get('type', 'html')  # 'html' or 'excel'
        folder_path = data.get('folder_path', '')  # Excel検索用のフォルダパス
        
        if not query:
            return JsonResponse({'success': False, 'error': '検索文字列が空です'})
        
        # Excelファイル検索
        if search_type == 'excel':
            return _search_excel_files(query, folder_path, request)
        
        # HTML要素検索（既存の処理）
        file_info = get_session_file_info(request)
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return JsonResponse({'success': False, 'error': 'HTMLエディタが初期化されていません'}, status=500)
        
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


def _search_excel_files(query: str, folder_path: str, request):
    """Excelファイルを検索"""
    try:
        import pandas as pd
        
        results = []
        excel_files = []
        
        # 検索対象のExcelファイルを決定
        if folder_path:
            # フォルダが指定されている場合、フォルダ内の全Excelファイルを検索
            folder = Path(folder_path)
            if not folder.exists() or not folder.is_dir():
                return JsonResponse({'success': False, 'error': f'フォルダが見つかりません: {folder_path}'}, status=404)
            
            excel_files = list(folder.glob('*.xlsx')) + list(folder.glob('*.xls'))
        else:
            # フォルダが指定されていない場合、選択されているExcelファイルを検索
            file_info = get_session_file_info(request)
            file_path = file_info.get('html_file_path')
            
            if file_path:
                file_path = Path(file_path)
                if file_path.exists() and (file_path.suffix.lower() in ['.xlsx', '.xls']):
                    excel_files = [file_path]
                else:
                    return JsonResponse({'success': False, 'error': '選択されているファイルがExcelファイルではありません'}, status=400)
            else:
                # ファイルが選択されていない場合、アップロードフォルダ内の全Excelファイルを検索
                excel_files = list(UPLOAD_DIR.glob('*.xlsx')) + list(UPLOAD_DIR.glob('*.xls'))
        
        if not excel_files:
            return JsonResponse({'success': True, 'results': [], 'message': '検索対象のExcelファイルが見つかりませんでした'})
        
        # 各Excelファイルを検索
        for excel_file in excel_files:
            try:
                # Excelファイルを読み込み
                df = pd.read_excel(excel_file, sheet_name=None, engine='openpyxl')
                
                file_results = []
                
                # 各シートを検索
                for sheet_name, sheet_df in df.items():
                    # データフレーム内でキーワードを検索
                    for row_idx, row in sheet_df.iterrows():
                        for col_idx, cell_value in enumerate(row):
                            if pd.notna(cell_value) and query.lower() in str(cell_value).lower():
                                file_results.append({
                                    'file': excel_file.name,
                                    'sheet': sheet_name,
                                    'row': int(row_idx) + 2,  # Excelの行番号（1ベース、ヘッダー行を考慮）
                                    'column': sheet_df.columns[col_idx] if col_idx < len(sheet_df.columns) else f'Column{col_idx + 1}',
                                    'value': str(cell_value)[:100],  # 最初の100文字
                                    'full_row': row.to_dict()
                                })
                
                if file_results:
                    results.extend(file_results)
                    
            except Exception as e:
                logger.error(f"Excelファイル検索エラー ({excel_file.name}): {e}")
                results.append({
                    'file': excel_file.name,
                    'error': f'ファイルの読み込みに失敗しました: {str(e)}'
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'total_files': len(excel_files),
            'matched_files': len(set(r.get('file') for r in results if 'file' in r))
        })
        
    except ImportError:
        return JsonResponse({'success': False, 'error': 'pandasまたはopenpyxlがインストールされていません'}, status=500)
    except Exception as e:
        logger.error(f"Excel検索エラー: {e}")
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
        
        # HTMLファイルまたはExcelファイルかチェック
        if not (filename.lower().endswith('.html') or filename.lower().endswith('.htm') or 
                filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls')):
            return JsonResponse({'success': False, 'error': 'HTMLファイルまたはExcelファイルのみアップロード可能です'}, status=400)
        
        # Excelファイルの場合はHTMLEditorを初期化しない
        is_excel = filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls')
        
        # アップロードフォルダに保存
        file_path = UPLOAD_DIR / filename
        with open(file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        
        # セッションにファイル情報を保存
        if not is_excel:
            # HTMLファイルの場合のみHTMLEditorを初期化
            html_editor = HTMLEditor(str(file_path))
            set_session_file_info(request, html_editor, file_path)
        else:
            # Excelファイルの場合はファイルパスのみ保存
            set_session_file_info(request, None, file_path)
        
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


@csrf_exempt
@require_http_methods(["POST"])
def validate(request):
    """HTMLの構文を検証"""
    import tempfile
    try:
        data = json.loads(request.body)
        if not data:
            return JsonResponse({'success': False, 'error': 'リクエストデータがありません'}, status=400)
        
        content = data.get('content', '')
        
        if not content:
            return JsonResponse({'success': False, 'error': 'コンテンツが空です'}, status=400)
        
        # 一時ファイルに保存して検証
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # HTMLEditorで検証
            temp_editor = HTMLEditor(temp_path)
            errors = temp_editor.validate_html()
            
            return JsonResponse({'success': True, 'errors': errors})
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    except Exception as e:
        logger.error(f"validate error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def diff_analysis(request):
    """27校の大学ホームページの差分を検出"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    import tempfile
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '').strip()
        options = data.get('options', {})
        
        # 空欄またはアップロードフォルダ指定の場合はアップロードフォルダを使用
        use_upload_dir = False
        if not directory or directory == '__upload__':
            directory = str(UPLOAD_DIR)
            use_upload_dir = True
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if not use_upload_dir and is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return JsonResponse({
                'success': False,
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }, status=400)
        
        # アップロードフォルダの場合はそのまま使用
        if use_upload_dir:
            dir_path = UPLOAD_DIR
        else:
            directory = directory.strip()
            if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
                directory = directory[0].upper() + directory[1:].replace('/', '\\')
            else:
                directory = directory.replace('\\\\', '\\').replace('/', '\\')
            
            try:
                if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                    dir_path = Path(directory)
                else:
                    dir_path = Path(directory).resolve()
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
                }, status=400)
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            if not is_cloud:
                error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            else:
                error_msg += f'\nパスの例: /tmp/html または /app/html\nLinux形式の絶対パスを指定してください'
            error_msg += '\n\n💡 ヒント: アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        
        if not dir_path.is_dir():
            return JsonResponse({
                'success': False,
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }, status=400)
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return JsonResponse({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}, status=404)
        
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
                continue
        
        if len(parsed_files) < 2:
            return JsonResponse({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}, status=400)
        
        # 差分を検出
        differences = _analyze_differences(parsed_files, options)
        
        # サマリーを生成
        summary = {
            'totalFiles': len(parsed_files),
            'structureDiffs': sum(1 for d in differences if d['type'] == 'structure'),
            'styleDiffs': sum(1 for d in differences if d['type'] == 'style'),
            'contentDiffs': sum(1 for d in differences if d['type'] == 'content'),
            'attributeDiffs': sum(1 for d in differences if d['type'] == 'attribute')
        }
        
        return JsonResponse({
            'success': True,
            'summary': summary,
            'differences': differences,
            'files': [f['filename'] for f in parsed_files]
        })
        
    except Exception as e:
        logger.error(f"diff_analysis error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _analyze_differences(parsed_files, options):
    """HTMLファイル間の差分を分析"""
    import time
    
    differences = []
    
    if len(parsed_files) < 2:
        return differences
    
    start_time = time.time()
    timeout = 60
    
    base_file = parsed_files[0]
    base_soup = base_file['soup']
    
    def get_all_elements(soup):
        """すべての要素を取得（最大1000要素に制限）"""
        elements = []
        if soup.body:
            body_elements = soup.body.find_all()
            max_elements = 1000
            if len(body_elements) > max_elements:
                important_elements = [e for e in body_elements if e.get('id') or e.get('class')]
                if len(important_elements) < max_elements:
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
    
    base_elements = get_all_elements(base_soup)
    processed_count = 0
    total_elements = len(base_elements)
    
    for base_elem in base_elements:
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
        
        selector = base_sig['tag']
        if base_sig['id']:
            selector = f"#{base_sig['id']}"
        elif base_sig['classes']:
            selector = base_sig['tag'] + '.' + '.'.join(base_sig['classes'][:3])
        
        matching_files = [base_file['filename']]
        different_files = []
        
        for other_file in parsed_files[1:]:
            if time.time() - start_time > timeout:
                break
            
            other_soup = other_file['soup']
            try:
                if base_sig['id']:
                    found = other_soup.find(id=base_sig['id'])
                elif base_sig['classes']:
                    found = other_soup.find(base_sig['tag'], class_=base_sig['classes'][0] if base_sig['classes'] else None)
                else:
                    found = other_soup.select_one(selector) if selector else None
                
                if found:
                    matching_files.append(other_file['filename'])
                    
                    if options.get('structure', True):
                        if found.name != base_elem.name:
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'structure',
                                'message': f"タグ名が異なります: {found.name} vs {base_elem.name}"
                            })
                    
                    if options.get('attributes', True):
                        base_attrs = set(base_elem.attrs.keys())
                        found_attrs = set(found.attrs.keys())
                        added = found_attrs - base_attrs
                        removed = base_attrs - found_attrs
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
                    if options.get('structure', True):
                        different_files.append({
                            'file': other_file['filename'],
                            'type': 'structure',
                            'message': '要素が見つかりません'
                        })
            except Exception:
                pass
        
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
        
        if len(differences) >= 1000:
            differences.append({
                'type': 'system',
                'element': 'limit',
                'description': f'差分が多すぎるため、処理を中断しました（最大1000件）。処理済み: {processed_count}/{total_elements}要素',
                'files': []
            })
            break
    
    # スタイルの差分をチェック
    if options.get('styles', True) and time.time() - start_time < timeout:
        base_styles = []
        if base_soup.head:
            base_styles.extend(base_soup.head.find_all('style'))
            base_styles.extend(base_soup.head.find_all('link', rel='stylesheet'))
        
        for other_file in parsed_files[1:]:
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


@csrf_exempt
@require_http_methods(["POST"])
def gcd_template(request):
    """差分を含めて最大公約数的な共通テンプレートを生成"""
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '')
        options = data.get('options', {})
        
        if not directory:
            return JsonResponse({'success': False, 'error': 'ディレクトリパスが指定されていません'}, status=400)
        
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return JsonResponse({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}, status=404)
        
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        if len(html_files) == 0:
            return JsonResponse({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}, status=404)
        
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
            except Exception:
                continue
        
        if len(parsed_files) < 2:
            return JsonResponse({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}, status=400)
        
        # 最大公約数テンプレートを生成（簡略版）
        gcd_template, stats = _generate_gcd_template(parsed_files, options)
        
        return JsonResponse({
            'success': True,
            'template': gcd_template,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"gcd_template error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _generate_gcd_template(parsed_files, options):
    """差分を含めて最大公約数的なテンプレートを生成（簡略版）"""
    if not parsed_files:
        return '', {
            'totalFiles': 0,
            'commonElements': 0,
            'variableElements': 0,
            'mergedElements': 0,
            'variables': []
        }
    
    # 最初のファイルを基準にする
    base_soup = BeautifulSoup(str(parsed_files[0]['soup']), 'html.parser')
    
    stats = {
        'totalFiles': len(parsed_files),
        'commonElements': 0,
        'variableElements': 0,
        'mergedElements': 0,
        'variables': []
    }
    
    # 簡略版: 最初のファイルをそのまま返す
    # 完全な実装は後で追加可能
    merged_html = str(base_soup)
    stats['mergedElements'] = len(base_soup.find_all())
    
    return merged_html, stats


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def template_merge(request):
    """複数のHTMLファイルを比較して共通テンプレートを生成"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    try:
        data = json.loads(request.body)
        files = data.get('files', [])
        options = data.get('options', {})
        
        if len(files) < 2:
            return JsonResponse({'success': False, 'error': '2つ以上のファイルを選択してください'}, status=400)
        
        parsed_files = []
        for file_path_str in files:
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                safe_filename = secure_filename(file_path_str)
                file_path = UPLOAD_DIR / safe_filename
            
            if not file_path.exists():
                return JsonResponse({'success': False, 'error': f'ファイルが見つかりません: {file_path_str}'}, status=404)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'ファイルの読み込みに失敗しました: {file_path_str} - {str(e)}'}, status=500)
        
        # 共通テンプレートを生成（簡略版）
        merged_template, stats = _merge_html_templates(parsed_files, options)
        
        return JsonResponse({
            'success': True,
            'template': merged_template,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"template_merge error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _merge_html_templates(parsed_files, options):
    """複数のHTMLファイルを統合して共通テンプレートを生成（簡略版）"""
    if not parsed_files:
        return '', {
            'totalFiles': 0,
            'commonElements': 0,
            'mergedElements': 0
        }
    
    # 最初のファイルを基準にする
    base_soup = BeautifulSoup(str(parsed_files[0]['soup']), 'html.parser')
    
    stats = {
        'totalFiles': len(parsed_files),
        'commonElements': 0,
        'mergedElements': len(base_soup.find_all())
    }
    
    # 簡略版: 最初のファイルをそのまま返す
    # 完全な実装は後で追加可能
    merged_html = str(base_soup)
    
    return merged_html, stats


@csrf_exempt
@require_http_methods(["POST"])
def generate_university_pages(request):
    """テンプレートを基に27大学のホームページを生成"""
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '')
        template = data.get('template', '')
        
        if not directory:
            return JsonResponse({'success': False, 'error': 'ディレクトリパスが指定されていません'}, status=400)
        
        if not template:
            return JsonResponse({'success': False, 'error': 'テンプレートが指定されていません'}, status=400)
        
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return JsonResponse({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}, status=404)
        
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        if len(html_files) == 0:
            return JsonResponse({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}, status=404)
        
        template_soup = BeautifulSoup(template, 'html.parser')
        output_dir = dir_path / 'generated_pages'
        output_dir.mkdir(exist_ok=True)
        
        generated_files = []
        success_count = 0
        failed_count = 0
        
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                original_soup = BeautifulSoup(original_content, 'html.parser')
                generated_soup = BeautifulSoup(str(template_soup), 'html.parser')
                
                # 簡略版: 元のファイルのコンテンツを適用
                content_area = generated_soup.find(id='content') or generated_soup.find(class_='content') or generated_soup.find('main')
                if content_area and original_soup.body:
                    content_area.clear()
                    content_area.append(original_soup.body)
                
                output_filename = f"generated_{file_path.stem}.html"
                output_path = output_dir / output_filename
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(str(generated_soup))
                
                generated_files.append(output_filename)
                success_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing {file_path.name}: {e}")
                continue
        
        return JsonResponse({
            'success': True,
            'generatedFiles': len(generated_files),
            'successCount': success_count,
            'failedCount': failed_count,
            'files': generated_files,
            'directory': str(output_dir)
        })
    except Exception as e:
        logger.error(f"generate_university_pages error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def download_university_pages(request):
    """生成された大学ページをZIPファイルとしてダウンロード"""
    import zipfile
    import tempfile
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '')
        
        if not directory:
            return JsonResponse({'success': False, 'error': 'ディレクトリパスが指定されていません'}, status=400)
        
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return JsonResponse({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}, status=404)
        
        generated_dir = dir_path / 'generated_pages'
        if not generated_dir.exists():
            return JsonResponse({'success': False, 'error': '生成されたページが見つかりません'}, status=404)
        
        # ZIPファイルを作成
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            zip_path = tmp_file.name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in generated_dir.glob('*.html'):
                zipf.write(file_path, file_path.name)
        
        # ZIPファイルをレスポンスとして返す
        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="university_pages.zip"'
        
        # 一時ファイルを削除
        try:
            os.unlink(zip_path)
        except Exception:
            pass
        
        return response
    except Exception as e:
        logger.error(f"download_university_pages error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# APIエンドポイント
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_list_directory_files(request):
    """指定ディレクトリ内のファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '').strip()
        
        if not directory:
            directory = str(UPLOAD_DIR)
        
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return JsonResponse({
                'success': False,
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。\n'
                        f'または、Linux形式の絶対パス（例: /tmp/html）を指定してください。'
            }, status=400)
        
        directory = directory.strip()
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        try:
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }, status=400)
        
        if not dir_path.exists():
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        
        if not dir_path.is_dir():
            return JsonResponse({
                'success': False,
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }, status=400)
        
        files = []
        
        # HTMLファイル
        for ext in ['*.html', '*.htm']:
            for file_path in dir_path.glob(ext):
                try:
                    file_info = {
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': 'html'
                    }
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        ids = set()
                        for elem in soup.find_all(id=True):
                            elem_id = elem.get('id')
                            if elem_id:
                                ids.add(str(elem_id))
                        
                        classes = set()
                        for elem in soup.find_all(class_=True):
                            elem_classes = elem.get('class', [])
                            if isinstance(elem_classes, list):
                                classes.update([str(c) for c in elem_classes if c])
                            elif elem_classes:
                                classes.add(str(elem_classes))
                        
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
                    except Exception:
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
        
        # その他のファイル
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
        
        files.sort(key=lambda x: x['name'])
        
        return JsonResponse({
            'success': True,
            'files': files,
            'count': len(files)
        })
    except Exception as e:
        logger.error(f"api_list_directory_files error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_config(request):
    """アプリケーション設定を取得"""
    try:
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        
        return JsonResponse({
            'success': True,
            'is_cloud': bool(is_cloud),
            'default_html_directory': None,
            'upload_folder': str(UPLOAD_DIR),
            'directory_info': None
        })
    except Exception as e:
        logger.error(f"api_config error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_check_directory(request):
    """指定されたディレクトリの存在確認とファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '').strip()
        
        if not directory:
            return JsonResponse({'success': False, 'error': 'ディレクトリパスを指定してください'}, status=400)
        
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return JsonResponse({
                'success': False,
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を指定してください。'
            }, status=400)
        
        directory = directory.strip()
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        try:
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }, status=400)
        
        if not dir_path.exists():
            return JsonResponse({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}, status=404)
        
        if not dir_path.is_dir():
            return JsonResponse({
                'success': False,
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }, status=400)
        
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        return JsonResponse({
            'success': True,
            'exists': True,
            'is_directory': True,
            'html_file_count': len(html_files),
            'html_files': [f.name for f in html_files[:10]]  # 最初の10個のみ
        })
    except Exception as e:
        logger.error(f"api_check_directory error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_load_comparison_files(request):
    """比較用ファイルリストを読み込む"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    try:
        data = json.loads(request.body)
        directory = data.get('directory', '').strip()
        
        if not directory:
            directory = str(UPLOAD_DIR)
        
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return JsonResponse({
                'success': False,
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }, status=400)
        
        directory = directory.strip()
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        try:
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }, status=400)
        
        if not dir_path.exists():
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        
        if not dir_path.is_dir():
            return JsonResponse({
                'success': False,
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }, status=400)
        
        html_files = []
        css_files = []
        
        for ext in ['*.html', '*.htm']:
            html_files.extend(dir_path.glob(ext))
            html_files.extend(dir_path.glob(ext.upper()))
        
        for ext in ['*.css']:
            css_files.extend(dir_path.glob(ext))
            css_files.extend(dir_path.glob(ext.upper()))
        
        html_files = sorted(html_files, key=lambda x: x.name)[:27]
        css_files = sorted(css_files, key=lambda x: x.name)
        
        html_css_map = {}
        for css_file in css_files:
            css_name = css_file.stem
            for html_file in html_files:
                html_name = html_file.stem
                if css_name == html_name or css_name in html_name or html_name in css_name:
                    if str(html_file) not in html_css_map:
                        html_css_map[str(html_file)] = []
                    html_css_map[str(html_file)].append(str(css_file))
        
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
            except Exception:
                continue
        
        for css_file in css_files:
            try:
                is_related = any(str(css_file) in file.get('relatedFiles', []) for file in files)
                if not is_related:
                    files.append({
                        'name': css_file.name,
                        'path': str(css_file),
                        'size': css_file.stat().st_size,
                        'type': 'css',
                        'relatedFiles': []
                    })
            except Exception:
                continue
        
        return JsonResponse({
            'success': True,
            'files': files,
            'count': len(files)
        })
    except Exception as e:
        logger.error(f"api_load_comparison_files error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_load_file_content(request):
    """ファイルの内容を読み込む"""
    try:
        file_path_str = request.GET.get('path', '')
        if not file_path_str:
            return JsonResponse({'success': False, 'error': 'ファイルパスが指定されていません'}, status=400)
        
        file_path = Path(file_path_str)
        if not file_path.is_absolute():
            safe_filename = secure_filename(file_path_str)
            file_path = UPLOAD_DIR / safe_filename
        
        if not file_path.exists():
            return JsonResponse({'success': False, 'error': f'ファイルが見つかりません: {file_path_str}'}, status=404)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return JsonResponse({
            'success': True,
            'content': content,
            'filename': file_path.name
        })
    except Exception as e:
        logger.error(f"api_load_file_content error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_compare_screens(request):
    """画面比較（簡略版）"""
    if request.method == 'OPTIONS':
        return HttpResponse('', status=200)
    
    try:
        data = json.loads(request.body)
        files = data.get('files', [])
        
        if len(files) < 2:
            return JsonResponse({'success': False, 'error': '2つ以上のファイルが必要です'}, status=400)
        
        # 簡略版: ファイルの存在確認のみ
        results = []
        for file_path_str in files:
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = UPLOAD_DIR / secure_filename(file_path_str)
            
            results.append({
                'path': file_path_str,
                'exists': file_path.exists(),
                'size': file_path.stat().st_size if file_path.exists() else 0
            })
        
        return JsonResponse({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"api_compare_screens error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _compare_html_structure(html_contents):
    """HTML構造を比較して差分を検出"""
    from bs4 import BeautifulSoup
    import re
    
    if len(html_contents) < 2:
        return {'html_diffs': 0, 'details': []}
    
    # 最初のファイルを基準にする
    base_soup = BeautifulSoup(html_contents[0], 'html.parser')
    base_elements = {}
    
    # 基準ファイルの要素を収集（タグ、ID、クラス、属性）
    for element in base_soup.find_all():
        tag = element.name
        elem_id = element.get('id', '')
        classes = ' '.join(sorted(element.get('class', [])))
        attrs = {k: v for k, v in element.attrs.items() if k not in ['id', 'class']}
        
        key = f"{tag}#{elem_id}.{classes}"
        if key not in base_elements:
            base_elements[key] = {
                'tag': tag,
                'id': elem_id,
                'classes': classes,
                'attrs': attrs,
                'count': 0
            }
        base_elements[key]['count'] += 1
    
    diffs = []
    for i, html_content in enumerate(html_contents[1:], 1):
        soup = BeautifulSoup(html_content, 'html.parser')
        compare_elements = {}
        
        for element in soup.find_all():
            tag = element.name
            elem_id = element.get('id', '')
            classes = ' '.join(sorted(element.get('class', [])))
            attrs = {k: v for k, v in element.attrs.items() if k not in ['id', 'class']}
            
            key = f"{tag}#{elem_id}.{classes}"
            if key not in compare_elements:
                compare_elements[key] = {
                    'tag': tag,
                    'id': elem_id,
                    'classes': classes,
                    'attrs': attrs,
                    'count': 0
                }
            compare_elements[key]['count'] += 1
        
        # 差分を検出
        file_diffs = 0
        for key, base_elem in base_elements.items():
            if key not in compare_elements:
                file_diffs += base_elem['count']
                diffs.append({
                    'file_index': i,
                    'type': 'missing',
                    'element': base_elem
                })
            elif compare_elements[key]['count'] != base_elem['count']:
                file_diffs += abs(compare_elements[key]['count'] - base_elem['count'])
                diffs.append({
                    'file_index': i,
                    'type': 'count_diff',
                    'base': base_elem,
                    'compare': compare_elements[key]
                })
        
        for key, compare_elem in compare_elements.items():
            if key not in base_elements:
                file_diffs += compare_elem['count']
                diffs.append({
                    'file_index': i,
                    'type': 'extra',
                    'element': compare_elem
                })
    
    return {'html_diffs': len(diffs), 'details': diffs[:100]}  # 最初の100件のみ


def _compare_css_structure(css_contents):
    """CSS構造を比較して差分を検出"""
    import re
    
    if len(css_contents) < 2:
        return {'css_diffs': 0, 'details': []}
    
    # CSSパーサー（簡略版）
    def parse_css(css_text):
        selectors = {}
        # セレクタとプロパティを抽出
        pattern = r'([^{]+)\{([^}]+)\}'
        for match in re.finditer(pattern, css_text):
            selector = match.group(1).strip()
            properties = {}
            for prop_match in re.finditer(r'([^:]+):([^;]+);?', match.group(2)):
                prop_name = prop_match.group(1).strip()
                prop_value = prop_match.group(2).strip()
                properties[prop_name] = prop_value
            selectors[selector] = properties
        return selectors
    
    base_css = parse_css(css_contents[0])
    diffs = []
    
    for i, css_content in enumerate(css_contents[1:], 1):
        compare_css = parse_css(css_content)
        file_diffs = 0
        
        # 基準にないセレクタ
        for selector, props in compare_css.items():
            if selector not in base_css:
                file_diffs += len(props)
                diffs.append({
                    'file_index': i,
                    'type': 'extra_selector',
                    'selector': selector,
                    'properties': props
                })
            else:
                # プロパティの差分
                base_props = base_css[selector]
                for prop_name, prop_value in props.items():
                    if prop_name not in base_props:
                        file_diffs += 1
                        diffs.append({
                            'file_index': i,
                            'type': 'extra_property',
                            'selector': selector,
                            'property': prop_name,
                            'value': prop_value
                        })
                    elif base_props[prop_name] != prop_value:
                        file_diffs += 1
                        diffs.append({
                            'file_index': i,
                            'type': 'value_diff',
                            'selector': selector,
                            'property': prop_name,
                            'base_value': base_props[prop_name],
                            'compare_value': prop_value
                        })
        
        # 基準にあるが比較ファイルにないセレクタ
        for selector, props in base_css.items():
            if selector not in compare_css:
                file_diffs += len(props)
                diffs.append({
                    'file_index': i,
                    'type': 'missing_selector',
                    'selector': selector,
                    'properties': props
                })
    
    return {'css_diffs': len(diffs), 'details': diffs[:100]}  # 最初の100件のみ


@csrf_exempt
@require_http_methods(["POST"])
def api_export_comparison_report(request):
    """比較レポートをエクスポート（HTML/CSS比較を含む）"""
    try:
        data = json.loads(request.body)
        files = data.get('files', [])
        
        if len(files) < 2:
            return JsonResponse({'success': False, 'error': '2つ以上のファイルが必要です'}, status=400)
        
        html_files = []
        css_files = []
        html_contents = []
        css_contents = []
        
        # ファイルを読み込んで分類
        for file_info in files:
            file_path_str = file_info.get('path', '')
            if not file_path_str:
                continue
            
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = UPLOAD_DIR / secure_filename(file_path_str)
            
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if file_path.suffix.lower() in ['.html', '.htm']:
                    html_files.append(file_info.get('name', file_path.name))
                    html_contents.append(content)
                elif file_path.suffix.lower() == '.css':
                    css_files.append(file_info.get('name', file_path.name))
                    css_contents.append(content)
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                continue
        
        # HTML/CSS比較を実行
        html_comparison = _compare_html_structure(html_contents) if len(html_contents) >= 2 else {'html_diffs': 0, 'details': []}
        css_comparison = _compare_css_structure(css_contents) if len(css_contents) >= 2 else {'css_diffs': 0, 'details': []}
        
        # CSVレポートを生成
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow(['比較レポート'])
        writer.writerow(['生成日時', str(datetime.now())])
        writer.writerow(['比較ファイル数', len(files)])
        writer.writerow(['HTMLファイル数', len(html_files)])
        writer.writerow(['CSSファイル数', len(css_files)])
        writer.writerow([])
        
        # HTML比較結果
        writer.writerow(['HTML比較結果'])
        writer.writerow(['差分数', html_comparison['html_diffs']])
        if html_comparison['details']:
            writer.writerow(['タイプ', 'ファイル', '要素情報'])
            for diff in html_comparison['details'][:50]:  # 最初の50件のみ
                file_name = html_files[diff.get('file_index', 0)] if diff.get('file_index', 0) < len(html_files) else 'Unknown'
                writer.writerow([diff.get('type', ''), file_name, str(diff.get('element', {}))])
        writer.writerow([])
        
        # CSS比較結果
        writer.writerow(['CSS比較結果'])
        writer.writerow(['差分数', css_comparison['css_diffs']])
        if css_comparison['details']:
            writer.writerow(['タイプ', 'ファイル', 'セレクタ/プロパティ', '詳細'])
            for diff in css_comparison['details'][:50]:  # 最初の50件のみ
                file_name = css_files[diff.get('file_index', 0)] if diff.get('file_index', 0) < len(css_files) else 'Unknown'
                selector = diff.get('selector', '')
                writer.writerow([diff.get('type', ''), file_name, selector, str(diff)])
        writer.writerow([])
        
        # ファイル一覧
        writer.writerow(['ファイル一覧'])
        writer.writerow(['ファイル名', 'パス', 'タイプ'])
        for file_info in files:
            writer.writerow([file_info.get('name', ''), file_info.get('path', ''), 'HTML' if file_info.get('path', '').endswith(('.html', '.htm')) else 'CSS'])
        
        csv_content = output.getvalue()
        output.close()
        
        return JsonResponse({
            'success': True,
            'report': csv_content,
            'html_diffs': html_comparison['html_diffs'],
            'css_diffs': css_comparison['css_diffs'],
            'html_files': html_files,
            'css_files': css_files
        })
    except Exception as e:
        logger.error(f"api_export_comparison_report error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
    """ページタイトル一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM page_titles ORDER BY display_order, title')
        titles = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return JsonResponse({'success': True, 'titles': titles})
    except Exception as e:
        logger.error(f"api_page_titles error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_university_pages(request, university_id):
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
        return JsonResponse({'success': True, 'pages': pages})
    except Exception as e:
        logger.error(f"api_university_pages error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def api_university_page_detail(request, university_id, page_title_id):
    """大学のページデータを取得・作成・更新"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if request.method == 'GET':
            conn.row_factory = sqlite3.Row
            cursor.execute('''
                SELECT upd.*, pt.title as page_title
                FROM university_page_data upd
                JOIN page_titles pt ON upd.page_title_id = pt.id
                WHERE upd.university_id = ? AND upd.page_title_id = ?
            ''', (university_id, page_title_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return JsonResponse({'success': True, 'page': dict(row)})
            else:
                return JsonResponse({'success': False, 'error': 'ページデータが見つかりません'}, status=404)
        
        elif request.method in ['POST', 'PUT']:
            data = json.loads(request.body)
            content = data.get('content', '')
            metadata = json.dumps(data.get('metadata', {}), ensure_ascii=False)
            
            cursor.execute('''
                INSERT OR REPLACE INTO university_page_data 
                (university_id, page_title_id, content, metadata, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (university_id, page_title_id, content, metadata))
            
            conn.commit()
            conn.close()
            return JsonResponse({'success': True})
    
    except Exception as e:
        logger.error(f"api_university_page_detail error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def api_university_config(request, university_id):
    """大学のJSON設定ファイルを管理"""
    try:
        config_file = UNIVERSITY_CONFIG_DIR / f'university_{university_id}.json'
        
        if request.method == 'GET':
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return JsonResponse({'success': True, 'config': config})
            else:
                return JsonResponse({'success': True, 'config': {
                    'layout': {},
                    'display_order': [],
                    'items': {}
                }})
        
        elif request.method in ['POST', 'PUT']:
            data = json.loads(request.body)
            config = data.get('config', {})
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return JsonResponse({'success': True})
    
    except Exception as e:
        logger.error(f"api_university_config error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_university_page(request):
    """共通テンプレートと大学データを統合してページを生成"""
    try:
        data = json.loads(request.body)
        university_id = data.get('university_id')
        page_title_id = data.get('page_title_id')
        template_html = data.get('template', '')
        
        if not university_id or not page_title_id or not template_html:
            return JsonResponse({'success': False, 'error': '必要なパラメータが不足しています'}, status=400)
        
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
        
        # レイアウト設定を適用（簡略版）
        layout = config.get('layout', {})
        display_order = config.get('display_order', [])
        items_config = config.get('items', {})
        
        generated_html = str(soup)
        
        return JsonResponse({
            'success': True,
            'html': generated_html
        })
    
    except Exception as e:
        logger.error(f"api_generate_university_page error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _load_yaml_config():
    """YAML設定ファイルを読み込む"""
    yaml_file = BASE_DIR / 'university_pages_config.yml'
    if yaml_file.exists():
        with open(yaml_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return None


def _generate_page_html(page_config, university_config, generation_settings):
    """ページHTMLを生成（簡略版）"""
    page_title = page_config.get('title', '')
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>{page_title}</title>
</head>
<body>
    <h1>{page_title}</h1>
    <p>このページは自動生成されました。</p>
</body>
</html>
"""
    return html


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_pages_from_yaml(request):
    """YAML設定ファイルを基に指定した大学または全大学の入学手続きWEBページを生成"""
    try:
        data = json.loads(request.body)
        university_codes = data.get('university_codes', [])
        output_directory = data.get('output_directory', '')
        
        yaml_config = _load_yaml_config()
        if not yaml_config:
            return JsonResponse({'success': False, 'error': 'YAML設定ファイルが見つかりません'}, status=404)
        
        default_page_titles = yaml_config.get('default_page_titles', [])
        universities_config = yaml_config.get('universities', [])
        generation_settings = yaml_config.get('generation_settings', {})
        page_mappings = yaml_config.get('page_mappings', [])
        
        if output_directory:
            output_dir = Path(output_directory)
        else:
            output_dir = UPLOAD_DIR / 'generated_university_pages'
        
        output_dir.mkdir(exist_ok=True, parents=True)
        
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if university_codes:
            placeholders = ','.join(['?' for _ in university_codes])
            cursor.execute(f'SELECT * FROM universities WHERE code IN ({placeholders})', university_codes)
        else:
            cursor.execute('SELECT * FROM universities ORDER BY code')
        
        universities = cursor.fetchall()
        conn.close()
        
        if not universities:
            return JsonResponse({'success': False, 'error': '対象となる大学が見つかりませんでした'}, status=404)
        
        generated_files = []
        total_pages = 0
        success_count = 0
        failed_count = 0
        
        for university in universities:
            university_code = university['code']
            university_name = university['name']
            university_id = university['id']
            
            university_config = None
            for univ_config in universities_config:
                if univ_config.get('code') == university_code:
                    university_config = univ_config
                    break
            
            univ_output_dir = output_dir / f"{university_code}_{university_name}"
            univ_output_dir.mkdir(exist_ok=True, parents=True)
            
            for page_config in default_page_titles:
                try:
                    page_id = page_config.get('id')
                    page_title = page_config.get('title', '')
                    
                    file_name = f"page_{page_id}_{page_title}.html"
                    route = f"/page-{page_id}"
                    for mapping in page_mappings:
                        if mapping.get('page_title_id') == page_id:
                            file_name = mapping.get('file_name', file_name)
                            route = mapping.get('route', route)
                            break
                    
                    html_content = _generate_page_html(page_config, university_config, generation_settings)
                    
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
                    logger.error(f"Error generating page {page_id} for {university_code}: {e}")
                    continue
        
        return JsonResponse({
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
        logger.error(f"api_generate_pages_from_yaml error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_pages_from_yaml_download(request):
    """YAML設定ファイルを基に生成したページをZIPファイルでダウンロード"""
    import zipfile
    import tempfile
    from datetime import datetime
    try:
        data = json.loads(request.body)
        output_directory = data.get('output_directory', '')
        
        if not output_directory:
            output_directory = str(UPLOAD_DIR / 'generated_university_pages')
        
        output_dir = Path(output_directory)
        if not output_dir.exists():
            return JsonResponse({'success': False, 'error': '出力ディレクトリが見つかりません'}, status=404)
        
        # ZIPファイルを作成
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            zip_path = tmp_file.name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in output_dir.rglob('*.html'):
                arcname = file_path.relative_to(output_dir)
                zip_file.write(file_path, arcname)
        
        # ZIPファイルをレスポンスとして返す
        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="university_pages_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"'
        
        # 一時ファイルを削除
        try:
            os.unlink(zip_path)
        except Exception:
            pass
        
        return response
    except Exception as e:
        logger.error(f"api_generate_pages_from_yaml_download error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
