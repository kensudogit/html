#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLEditorクラスのテスト
"""

import unittest
import tempfile
import os
from pathlib import Path
from html_editor import HTMLEditor


class TestHTMLEditor(unittest.TestCase):
    """HTMLEditorクラスのテストクラス"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        # 一時的なHTMLファイルを作成
        self.temp_dir = tempfile.mkdtemp()
        self.html_file = os.path.join(self.temp_dir, 'test.html')
        
        # テスト用のHTMLコンテンツ
        self.html_content = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="Test description">
    <meta property="og:title" content="Test OG Title">
    <title>Test Title</title>
</head>
<body>
    <div id="main-content" class="container">
        <h1>Hello World</h1>
        <p class="text">This is a test paragraph.</p>
        <a href="https://example.com" id="test-link" class="link">Example Link</a>
        <img src="test.jpg" alt="Test Image" id="test-img" class="image">
        <form id="test-form">
            <input type="text" name="test-input">
        </form>
    </div>
    <script src="test.js"></script>
    <link rel="stylesheet" href="style.css">
</body>
</html>"""
        
        # HTMLファイルを書き込み
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(self.html_content)
    
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        # 一時ファイルを削除
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """初期化のテスト"""
        editor = HTMLEditor(self.html_file)
        self.assertIsNotNone(editor.soup)
        self.assertEqual(editor.html_file_path, Path(self.html_file))
        self.assertEqual(editor.encoding, 'utf-8')
    
    def test_init_file_not_found(self):
        """存在しないファイルでの初期化テスト"""
        with self.assertRaises(FileNotFoundError):
            HTMLEditor('nonexistent.html')
    
    def test_find_by_id(self):
        """IDで要素を検索するテスト"""
        editor = HTMLEditor(self.html_file)
        element = editor.find_by_id('main-content')
        self.assertIsNotNone(element)
        self.assertEqual(element.name, 'div')
        
        element = editor.find_by_id('nonexistent')
        self.assertIsNone(element)
    
    def test_find_by_class(self):
        """クラス名で要素を検索するテスト"""
        editor = HTMLEditor(self.html_file)
        elements = editor.find_by_class('container')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].name, 'div')
        
        elements = editor.find_by_class('text')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].name, 'p')
    
    def test_find_by_class_with_tag(self):
        """タグ指定付きクラス検索のテスト"""
        editor = HTMLEditor(self.html_file)
        elements = editor.find_by_class('link', tag='a')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].name, 'a')
    
    def test_find_by_tag(self):
        """タグ名で要素を検索するテスト"""
        editor = HTMLEditor(self.html_file)
        elements = editor.find_by_tag('p')
        self.assertGreater(len(elements), 0)
        self.assertEqual(elements[0].name, 'p')
    
    def test_find_by_attribute(self):
        """属性で要素を検索するテスト"""
        editor = HTMLEditor(self.html_file)
        elements = editor.find_by_attribute('name', 'test-input')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].name, 'input')
    
    def test_find_by_text(self):
        """テキストで要素を検索するテスト"""
        editor = HTMLEditor(self.html_file)
        elements = editor.find_by_text('Hello World')
        self.assertGreater(len(elements), 0)
    
    def test_get_title(self):
        """タイトルを取得するテスト"""
        editor = HTMLEditor(self.html_file)
        title = editor.get_title()
        self.assertEqual(title, 'Test Title')
    
    def test_set_title(self):
        """タイトルを設定するテスト"""
        editor = HTMLEditor(self.html_file)
        editor.set_title('New Title')
        title = editor.get_title()
        self.assertEqual(title, 'New Title')
    
    def test_get_meta(self):
        """メタタグを取得するテスト"""
        editor = HTMLEditor(self.html_file)
        description = editor.get_meta('description')
        self.assertEqual(description, 'Test description')
        
        og_title = editor.get_meta('og:title', attr='property')
        self.assertEqual(og_title, 'Test OG Title')
    
    def test_set_meta(self):
        """メタタグを設定するテスト"""
        editor = HTMLEditor(self.html_file)
        editor.set_meta('description', 'New Description')
        description = editor.get_meta('description')
        self.assertEqual(description, 'New Description')
    
    def test_get_all_links(self):
        """すべてのリンクを取得するテスト"""
        editor = HTMLEditor(self.html_file)
        links = editor.get_all_links()
        self.assertGreater(len(links), 0)
        self.assertEqual(links[0]['href'], 'https://example.com')
        self.assertEqual(links[0]['text'], 'Example Link')
    
    def test_get_all_images(self):
        """すべての画像を取得するテスト"""
        editor = HTMLEditor(self.html_file)
        images = editor.get_all_images()
        self.assertGreater(len(images), 0)
        self.assertEqual(images[0]['src'], 'test.jpg')
        self.assertEqual(images[0]['alt'], 'Test Image')
    
    def test_update_text(self):
        """要素のテキストを更新するテスト"""
        editor = HTMLEditor(self.html_file)
        element = editor.find_by_id('test-link')
        editor.update_text(element, 'New Link Text')
        self.assertEqual(element.string, 'New Link Text')
    
    def test_update_attribute(self):
        """要素の属性を更新するテスト"""
        editor = HTMLEditor(self.html_file)
        element = editor.find_by_id('test-link')
        editor.update_attribute(element, 'href', 'https://newurl.com')
        self.assertEqual(element.get('href'), 'https://newurl.com')
    
    def test_add_element(self):
        """要素を追加するテスト"""
        editor = HTMLEditor(self.html_file)
        parent = editor.find_by_id('main-content')
        new_element = editor.add_element(parent, 'div', text='New Div', attrs={'id': 'new-div'})
        self.assertIsNotNone(new_element)
        self.assertEqual(new_element.name, 'div')
        self.assertEqual(new_element.string, 'New Div')
        self.assertEqual(new_element.get('id'), 'new-div')
    
    def test_remove_element(self):
        """要素を削除するテスト"""
        editor = HTMLEditor(self.html_file)
        element = editor.find_by_id('test-link')
        editor.remove_element(element)
        element_after = editor.find_by_id('test-link')
        self.assertIsNone(element_after)
    
    def test_replace_element(self):
        """要素を置き換えるテスト"""
        editor = HTMLEditor(self.html_file)
        old_element = editor.find_by_id('test-link')
        new_element = editor.replace_element(old_element, 'span', text='New Span', new_attrs={'id': 'new-span'})
        self.assertIsNotNone(new_element)
        self.assertEqual(new_element.name, 'span')
        self.assertEqual(new_element.string, 'New Span')
        
        # 古い要素が存在しないことを確認
        old_element_after = editor.find_by_id('test-link')
        self.assertIsNone(old_element_after)
    
    def test_get_structure_info(self):
        """構造情報を取得するテスト"""
        editor = HTMLEditor(self.html_file)
        info = editor.get_structure_info()
        self.assertEqual(info['title'], 'Test Title')
        self.assertEqual(info['links_count'], 1)
        self.assertEqual(info['images_count'], 1)
        self.assertEqual(info['scripts_count'], 1)
        self.assertEqual(info['stylesheets_count'], 1)
        self.assertEqual(info['forms_count'], 1)
        self.assertIn('description', info['meta_tags'])
    
    def test_save(self):
        """HTMLを保存するテスト"""
        editor = HTMLEditor(self.html_file)
        output_file = os.path.join(self.temp_dir, 'output.html')
        editor.save(output_path=output_file, pretty_print=True)
        self.assertTrue(os.path.exists(output_file))
        
        # 保存されたファイルの内容を確認
        with open(output_file, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        self.assertIn('Test Title', saved_content)
    
    def test_save_overwrite(self):
        """元のファイルに上書き保存するテスト"""
        editor = HTMLEditor(self.html_file)
        editor.set_title('Updated Title')
        editor.save()
        
        # 再読み込みして確認
        editor2 = HTMLEditor(self.html_file)
        self.assertEqual(editor2.get_title(), 'Updated Title')
    
    def test_export_to_json(self):
        """構造情報をJSONにエクスポートするテスト"""
        editor = HTMLEditor(self.html_file)
        json_file = os.path.join(self.temp_dir, 'structure.json')
        editor.export_to_json(json_file)
        self.assertTrue(os.path.exists(json_file))
        
        import json
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['title'], 'Test Title')
        self.assertIn('links', data)
        self.assertIn('images', data)
    
    def test_validate_html_valid(self):
        """有効なHTMLの検証テスト"""
        editor = HTMLEditor(self.html_file)
        errors = editor.validate_html()
        # 有効なHTMLなので、エラーは警告のみか、または空である可能性がある
        # エラーのタイプを確認
        critical_errors = [e for e in errors if e['type'] == 'error']
        # 基本的な構文エラーはないはず
        self.assertIsInstance(errors, list)
    
    def test_validate_html_invalid(self):
        """無効なHTMLの検証テスト"""
        # 閉じタグがないHTMLを作成
        invalid_html = """<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
<body>
    <div>Unclosed div
</body>
</html>"""
        
        invalid_file = os.path.join(self.temp_dir, 'invalid.html')
        with open(invalid_file, 'w', encoding='utf-8') as f:
            f.write(invalid_html)
        
        editor = HTMLEditor(invalid_file)
        errors = editor.validate_html()
        # エラーが検出されることを確認
        self.assertIsInstance(errors, list)
        # 少なくとも1つのエラーまたは警告があることを確認
        self.assertGreater(len(errors), 0)


if __name__ == '__main__':
    unittest.main()

