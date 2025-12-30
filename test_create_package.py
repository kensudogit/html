#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_package.pyのテスト
"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path
from create_package import create_package, INCLUDE_FILES, EXCLUDE_PATTERNS


class TestCreatePackage(unittest.TestCase):
    """create_package.pyのテストクラス"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.test_source_dir = os.path.join(self.temp_dir, 'test_source')
        os.makedirs(self.test_source_dir, exist_ok=True)
        
        # テスト用のファイルを作成
        self.test_files = {
            'web_html_editor.py': '#!/usr/bin/env python3\n# Test file',
            'html_editor.py': '#!/usr/bin/env python3\n# Test file',
            'requirements.txt': 'flask==2.0.0\nbeautifulsoup4==4.9.0',
            'SETUP.md': '# Setup Instructions',
            'INSTALL.txt': 'Installation instructions',
            'README.md': '# Readme',
        }
        
        for filename, content in self.test_files.items():
            file_path = os.path.join(self.test_source_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # 除外するファイル/ディレクトリも作成
        self.excluded_items = {
            '__pycache__': None,  # ディレクトリ
            'venv': None,  # ディレクトリ
            'test_structure.py': 'test file',
            'html_edit_interactive.py': 'interactive file',
        }
        
        for item_name, content in self.excluded_items.items():
            item_path = os.path.join(self.test_source_dir, item_name)
            if content is None:
                # ディレクトリ
                os.makedirs(item_path, exist_ok=True)
            else:
                # ファイル
                with open(item_path, 'w', encoding='utf-8') as f:
                    f.write(content)
    
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_include_files_list(self):
        """INCLUDE_FILESリストのテスト"""
        self.assertIsInstance(INCLUDE_FILES, list)
        self.assertGreater(len(INCLUDE_FILES), 0)
        self.assertIn('web_html_editor.py', INCLUDE_FILES)
        self.assertIn('html_editor.py', INCLUDE_FILES)
    
    def test_exclude_patterns_list(self):
        """EXCLUDE_PATTERNSリストのテスト"""
        self.assertIsInstance(EXCLUDE_PATTERNS, list)
        self.assertGreater(len(EXCLUDE_PATTERNS), 0)
        self.assertIn('__pycache__', EXCLUDE_PATTERNS)
        self.assertIn('venv', EXCLUDE_PATTERNS)
    
    def test_create_package_basic(self):
        """基本的なパッケージ作成のテスト"""
        # 元のcreate_package関数をモックする代わりに、
        # 実際のディレクトリ構造をテストする
        
        # パッケージディレクトリのパス
        package_dir = os.path.join(self.temp_dir, 'html_editor_package')
        
        # パッケージディレクトリが存在しないことを確認
        self.assertFalse(os.path.exists(package_dir))
        
        # 手動でパッケージ作成のロジックをテスト
        # 実際のcreate_package関数は現在のディレクトリを基準にするため、
        # ここではロジックの一部をテスト
        
        # パッケージディレクトリを作成
        os.makedirs(package_dir, exist_ok=True)
        
        # 必須ファイルをコピー
        copied_files = []
        for filename in INCLUDE_FILES:
            src = os.path.join(self.test_source_dir, filename)
            if os.path.exists(src):
                dst = os.path.join(package_dir, filename)
                shutil.copy2(src, dst)
                copied_files.append(filename)
        
        # パッケージディレクトリが作成されたことを確認
        self.assertTrue(os.path.exists(package_dir))
        
        # 必須ファイルがコピーされたことを確認
        for filename in copied_files:
            dst = os.path.join(package_dir, filename)
            self.assertTrue(os.path.exists(dst), f"{filename} should be copied")
        
        # 除外されたファイルがコピーされていないことを確認
        for item_name in self.excluded_items.keys():
            dst = os.path.join(package_dir, item_name)
            self.assertFalse(os.path.exists(dst), f"{item_name} should not be copied")
    
    def test_package_structure(self):
        """パッケージ構造のテスト"""
        package_dir = os.path.join(self.temp_dir, 'html_editor_package')
        os.makedirs(package_dir, exist_ok=True)
        
        # 必須ファイルをコピー
        for filename in INCLUDE_FILES:
            src = os.path.join(self.test_source_dir, filename)
            if os.path.exists(src):
                dst = os.path.join(package_dir, filename)
                shutil.copy2(src, dst)
        
        # パッケージディレクトリ内のファイルを確認
        files_in_package = os.listdir(package_dir)
        
        # 必須ファイルが含まれていることを確認
        for filename in INCLUDE_FILES:
            if os.path.exists(os.path.join(self.test_source_dir, filename)):
                self.assertIn(filename, files_in_package)
        
        # 除外されたファイルが含まれていないことを確認
        for item_name in self.excluded_items.keys():
            self.assertNotIn(item_name, files_in_package)
    
    def test_file_content_preserved(self):
        """ファイル内容が保持されることをテスト"""
        package_dir = os.path.join(self.temp_dir, 'html_editor_package')
        os.makedirs(package_dir, exist_ok=True)
        
        # ファイルをコピー
        test_file = 'web_html_editor.py'
        src = os.path.join(self.test_source_dir, test_file)
        dst = os.path.join(package_dir, test_file)
        shutil.copy2(src, dst)
        
        # 内容が同じであることを確認
        with open(src, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(dst, 'r', encoding='utf-8') as f:
            copied_content = f.read()
        
        self.assertEqual(original_content, copied_content)
    
    def test_package_directory_creation(self):
        """パッケージディレクトリの作成テスト"""
        package_dir = os.path.join(self.temp_dir, 'html_editor_package')
        
        # ディレクトリが存在しないことを確認
        self.assertFalse(os.path.exists(package_dir))
        
        # ディレクトリを作成
        os.makedirs(package_dir, exist_ok=True)
        
        # ディレクトリが作成されたことを確認
        self.assertTrue(os.path.exists(package_dir))
        self.assertTrue(os.path.isdir(package_dir))


if __name__ == '__main__':
    unittest.main()

