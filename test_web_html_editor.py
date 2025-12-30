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
        self.assertIn(b'HTMLエディタ', response.data)
    
    def test_index_with_session_file(self):
        """セッションにファイルがある場合のメインページテスト"""
        with self.client.session_transaction() as sess:
            # セッションにファイル情報を設定
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Title', response.data)
    
    def test_content_route_no_file(self):
        """ファイルが選択されていない場合のcontentルートテスト"""
        response = self.client.get('/content')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('ファイルが選択されていません', data['error'])
    
    def test_content_route_with_file(self):
        """ファイルが選択されている場合のcontentルートテスト"""
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
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
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
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
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
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
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
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
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
        response = self.client.post('/search',
                                   data=json.dumps({'query': ''}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_search_route_by_id(self):
        """IDで検索するsearchルートテスト"""
        with self.client.session_transaction() as sess:
            from web_html_editor import set_session_file_info
            from html_editor import HTMLEditor
            
            editor = HTMLEditor(self.html_file)
            set_session_file_info(editor, self.html_file)
        
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
        # テスト用のHTMLファイルを準備
        test_html = '<html><head><title>Uploaded</title></head><body>Uploaded Content</body></html>'
        
        response = self.client.post('/upload',
                                   data={'file': (test_html.encode('utf-8'), 'test_upload.html')},
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


if __name__ == '__main__':
    unittest.main()

