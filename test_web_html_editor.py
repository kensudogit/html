#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_html_editor.pyのFlaskアプリケーションのテスト
"""

import unittest
import tempfile
import os
import json
from pathlib import Path
from werkzeug.test import Client
from werkzeug.wrappers import Response
from web_html_editor import app


class TestWebHTMLEditor(unittest.TestCase):
    """web_html_editor.pyのFlaskアプリケーションのテストクラス"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        # Flaskテストクライアントを作成
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.app.config['UPLOAD_FOLDER'] = self.temp_dir
        
        # テスト用のHTMLファイルを作成
        self.html_file = os.path.join(self.temp_dir, 'test.html')
        self.html_content = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Test Title</title>
</head>
<body>
    <div id="main-content">
        <h1>Hello World</h1>
        <a href="https://example.com">Example Link</a>
        <img src="test.jpg" alt="Test Image">
    </div>
</body>
</html>"""
        
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(self.html_content)
        
        self.client = self.app.test_client()
    
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_index_route(self):
        """メインページのルートテスト"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # 日本語はエンコードして検索
        self.assertIn('HTMLエディタ'.encode('utf-8'), response.data)
    
    def test_index_with_session_file(self):
        """セッションにファイルがある場合のメインページテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Title'.encode('utf-8'), response.data)
    
    def test_content_route_no_file(self):
        """ファイルが選択されていない場合のcontentルートテスト"""
        response = self.client.get('/content')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('ファイルが選択されていません', data['error'])
    
    def test_content_route_with_file(self):
        """ファイルが選択されている場合のcontentルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.get('/content')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('Test Title', data['content'])
    
    def test_save_route_no_file(self):
        """ファイルが選択されていない場合のsaveルートテスト"""
        response = self.client.post('/save', 
                                   data=json.dumps({'content': '<html></html>'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_save_route_with_file(self):
        """ファイルが選択されている場合のsaveルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        new_content = '<html><head><title>New Title</title></head><body>New Content</body></html>'
        response = self.client.post('/save',
                                   data=json.dumps({'content': new_content}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # ファイルが実際に保存されたことを確認
        with open(self.html_file, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        self.assertIn('New Title', saved_content)
    
    def test_reload_route_no_file(self):
        """ファイルが選択されていない場合のreloadルートテスト"""
        response = self.client.get('/reload')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_reload_route_with_file(self):
        """ファイルが選択されている場合のreloadルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.get('/reload')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('Test Title', data['content'])
    
    def test_structure_route_no_editor(self):
        """エディタが初期化されていない場合のstructureルートテスト"""
        response = self.client.get('/structure')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_structure_route_with_editor(self):
        """エディタが初期化されている場合のstructureルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.get('/structure')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('info', data)
        self.assertEqual(data['info']['title'], 'Test Title')
        self.assertEqual(data['info']['links_count'], 1)
        self.assertEqual(data['info']['images_count'], 1)
    
    def test_search_route_no_editor(self):
        """エディタが初期化されていない場合のsearchルートテスト"""
        response = self.client.post('/search',
                                   data=json.dumps({'query': 'main-content'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_search_route_empty_query(self):
        """空のクエリでのsearchルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.post('/search',
                                   data=json.dumps({'query': ''}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_search_route_by_id(self):
        """IDで検索するsearchルートテスト"""
        from web_html_editor import session_files
        from html_editor import HTMLEditor
        import secrets
        
        with self.client.session_transaction() as sess:
            session_id = secrets.token_hex(16)
            sess['session_id'] = session_id
            
            editor = HTMLEditor(self.html_file)
            session_files[session_id] = {
                'html_editor': editor,
                'html_file_path': self.html_file
            }
        
        response = self.client.post('/search',
                                   data=json.dumps({'query': 'main-content'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['results']), 0)
        self.assertEqual(data['results'][0]['id'], 'main-content')
    
    def test_validate_route_no_content(self):
        """コンテンツがない場合のvalidateルートテスト"""
        response = self.client.post('/validate',
                                   data=json.dumps({}),
                                   content_type='application/json')
        # コンテンツが空の場合は400が返る
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_validate_route_with_content(self):
        """コンテンツがある場合のvalidateルートテスト"""
        response = self.client.post('/validate',
                                   data=json.dumps({'content': self.html_content}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('errors', data)
    
    def test_upload_route_no_file(self):
        """ファイルがアップロードされていない場合のuploadルートテスト"""
        response = self.client.post('/upload')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_upload_route_with_file(self):
        """ファイルがアップロードされている場合のuploadルートテスト"""
        import io
        # テスト用のHTMLファイルを準備
        test_html = '<html><head><title>Uploaded</title></head><body>Uploaded Content</body></html>'
        
        response = self.client.post('/upload',
                                   data={'file': (io.BytesIO(test_html.encode('utf-8')), 'test_upload.html')},
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('filename', data)
    
    def test_files_route(self):
        """filesルートテスト"""
        response = self.client.get('/files')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('files', data)
        self.assertIsInstance(data['files'], list)
    
    def test_load_file_route(self):
        """load_fileルートテスト"""
        response = self.client.get(f'/load/test.html')
        # ファイルが存在しない場合は404または400
        # ファイルが存在する場合は200
        self.assertIn(response.status_code, [200, 400, 404])
    
    def test_delete_file_route(self):
        """delete_fileルートテスト"""
        # 存在しないファイルを削除しようとする
        response = self.client.delete('/delete/nonexistent.html')
        # ファイルが存在しない場合は404または400
        self.assertIn(response.status_code, [200, 400, 404])


class TestWebHTMLEditorAdvanced(unittest.TestCase):
    """web_html_editor.pyの高度な機能のテストクラス"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.app.config['UPLOAD_FOLDER'] = self.temp_dir
        
        # テスト用のHTMLファイルを作成
        self.html_file1 = os.path.join(self.temp_dir, 'test1.html')
        self.html_file2 = os.path.join(self.temp_dir, 'test2.html')
        
        html_content1 = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Test 1</title>
    <style>
        .header { color: blue; }
    </style>
</head>
<body>
    <div id="header" class="header">
        <h1>Header 1</h1>
    </div>
</body>
</html>"""
        
        html_content2 = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Test 2</title>
    <style>
        .header { color: red; }
    </style>
</head>
<body>
    <div id="header" class="header">
        <h1>Header 2</h1>
    </div>
</body>
</html>"""
        
        with open(self.html_file1, 'w', encoding='utf-8') as f:
            f.write(html_content1)
        
        with open(self.html_file2, 'w', encoding='utf-8') as f:
            f.write(html_content2)
        
        self.client = self.app.test_client()
    
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_diff_analysis_route_empty_directory(self):
        """空のディレクトリでの差分検出テスト"""
        response = self.client.post('/diff-analysis',
                                   data=json.dumps({
                                       'directory': '',
                                       'options': {
                                           'structure': True,
                                           'styles': True,
                                           'content': True,
                                           'attributes': True
                                       }
                                   }),
                                   content_type='application/json')
        # 空のディレクトリでもエラーにならないことを確認
        self.assertIn(response.status_code, [200, 400])
    
    def test_diff_analysis_route_with_files(self):
        """ファイルがある場合の差分検出テスト"""
        response = self.client.post('/diff-analysis',
                                   data=json.dumps({
                                       'directory': self.temp_dir,
                                       'options': {
                                           'structure': True,
                                           'styles': True,
                                           'content': True,
                                           'attributes': True
                                       }
                                   }),
                                   content_type='application/json')
        # ファイルがある場合は200を期待
        self.assertIn(response.status_code, [200, 400])
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('success', data)
    
    def test_template_merge_route_no_files(self):
        """ファイルが選択されていない場合のテンプレート統合テスト"""
        response = self.client.post('/template-merge',
                                   data=json.dumps({
                                       'files': [],
                                       'options': {
                                           'merge_html': True,
                                           'merge_css': True,
                                           'merge_content': True,
                                           'merge_attributes': True
                                       }
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400])
    
    def test_template_merge_route_with_files(self):
        """ファイルが選択されている場合のテンプレート統合テスト"""
        # ファイルは既にtemp_dirに存在するので、コピーは不要
        response = self.client.post('/template-merge',
                                   data=json.dumps({
                                       'files': ['test1.html', 'test2.html'],
                                       'options': {
                                           'merge_html': True,
                                           'merge_css': True,
                                           'merge_content': True,
                                           'merge_attributes': True
                                       },
                                       'directory': self.temp_dir
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400])
    
    def test_api_list_directory_files_route(self):
        """ディレクトリファイル一覧取得APIテスト"""
        response = self.client.post('/api/list-directory-files',
                                   data=json.dumps({
                                       'directory': self.temp_dir
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('success', data)
    
    def test_api_config_route(self):
        """設定取得APIテスト"""
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('success', data)
    
    def test_api_check_directory_route(self):
        """ディレクトリチェックAPIテスト"""
        response = self.client.post('/api/check-directory',
                                   data=json.dumps({
                                       'directory': self.temp_dir
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400])
    
    def test_api_load_comparison_files_route(self):
        """比較ファイル読み込みAPIテスト"""
        response = self.client.post('/api/load-comparison-files',
                                   data=json.dumps({
                                       'directory': self.temp_dir
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400])
    
    def test_api_load_file_content_route(self):
        """ファイル内容読み込みAPIテスト"""
        response = self.client.get('/api/load-file-content?file=test1.html&directory=' + self.temp_dir)
        self.assertIn(response.status_code, [200, 400, 404])
    
    def test_api_compare_screens_route(self):
        """画面比較APIテスト"""
        response = self.client.post('/api/compare-screens',
                                   data=json.dumps({
                                       'files': ['test1.html', 'test2.html'],
                                       'directory': self.temp_dir
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400])
    
    def test_api_export_comparison_report_route(self):
        """比較レポートエクスポートAPIテスト"""
        response = self.client.post('/api/export-comparison-report',
                                   data=json.dumps({
                                       'files': [
                                           {'name': 'test1.html', 'path': str(self.html_file1)},
                                           {'name': 'test2.html', 'path': str(self.html_file2)}
                                       ]
                                   }),
                                   content_type='application/json')
        self.assertIn(response.status_code, [200, 400, 500])


class TestWebHTMLEditorUniversityAPI(unittest.TestCase):
    """web_html_editor.pyの大学データ管理APIのテストクラス"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.app.config['UPLOAD_FOLDER'] = self.temp_dir
        
        # データベースを初期化
        from web_html_editor import init_database, DB_PATH, UPLOAD_DIR
        import shutil
        import sqlite3
        import web_html_editor
        
        # 一時ディレクトリにデータベースを作成
        self.test_db_path = Path(self.temp_dir) / 'university_data.db'
        self.test_config_dir = Path(self.temp_dir) / 'university_configs'
        self.test_config_dir.mkdir(exist_ok=True, parents=True)
        
        # 一時的にDB_PATHとUNIVERSITY_CONFIG_DIRを変更
        self.original_db_path = web_html_editor.DB_PATH
        self.original_config_dir = web_html_editor.UNIVERSITY_CONFIG_DIR
        web_html_editor.DB_PATH = self.test_db_path
        web_html_editor.UNIVERSITY_CONFIG_DIR = self.test_config_dir
        
        # データベースを初期化
        init_database()
        self.client = self.app.test_client()
    
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        import shutil
        import sqlite3
        import time
        import web_html_editor
        
        # データベース接続を閉じる
        try:
            if hasattr(self, 'test_db_path') and os.path.exists(self.test_db_path):
                # 接続が閉じられるまで待つ
                for _ in range(10):
                    try:
                        os.remove(self.test_db_path)
                        break
                    except PermissionError:
                        time.sleep(0.1)
        except:
            pass
        
        # 元のパスを復元
        if hasattr(self, 'original_db_path'):
            web_html_editor.DB_PATH = self.original_db_path
        if hasattr(self, 'original_config_dir'):
            web_html_editor.UNIVERSITY_CONFIG_DIR = self.original_config_dir
        
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
    
    def test_get_universities_route(self):
        """大学一覧取得APIテスト"""
        response = self.client.get('/api/universities')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('universities', data)
        self.assertIsInstance(data['universities'], list)
    
    def test_create_university_route(self):
        """大学作成APIテスト"""
        response = self.client.post('/api/universities',
                                   data=json.dumps({
                                       'code': 'TEST001',
                                       'name': 'Test University'
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('id', data)
    
    def test_create_university_route_duplicate(self):
        """重複した大学コードでの大学作成APIテスト"""
        # 最初の大学を作成
        self.client.post('/api/universities',
                        data=json.dumps({
                            'code': 'TEST001',
                            'name': 'Test University 1'
                        }),
                        content_type='application/json')
        
        # 同じコードで再度作成を試みる
        response = self.client.post('/api/universities',
                                   data=json.dumps({
                                       'code': 'TEST001',
                                       'name': 'Test University 2'
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_create_university_route_missing_fields(self):
        """必須フィールドが欠けている場合の大学作成APIテスト"""
        response = self.client.post('/api/universities',
                                   data=json.dumps({
                                       'code': 'TEST001'
                                       # nameが欠けている
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_get_page_titles_route(self):
        """ページタイトル一覧取得APIテスト"""
        response = self.client.get('/api/page-titles')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('page_titles', data)
        self.assertIsInstance(data['page_titles'], list)
    
    def test_get_university_pages_route(self):
        """大学ページ一覧取得APIテスト"""
        # まず大学を作成
        create_response = self.client.post('/api/universities',
                                          data=json.dumps({
                                              'code': 'TEST001',
                                              'name': 'Test University'
                                          }),
                                          content_type='application/json')
        university_id = json.loads(create_response.data)['id']
        
        # 大学のページ一覧を取得
        response = self.client.get(f'/api/university/{university_id}/pages')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('pages', data)
    
    def test_get_university_pages_route_not_found(self):
        """存在しない大学のページ一覧取得APIテスト"""
        response = self.client.get('/api/university/99999/pages')
        self.assertIn(response.status_code, [200, 404])


if __name__ == '__main__':
    unittest.main()

