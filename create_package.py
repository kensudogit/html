#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTMLエディタ パッケージ作成スクリプト
他のPCにコピーして使用できるパッケージを作成します。
"""

import os
import shutil
import sys
from pathlib import Path

# パッケージ名
PACKAGE_NAME = "html_editor_package"

# 含めるファイル
INCLUDE_FILES = [
    "web_html_editor.py",
    "html_editor.py",
    "requirements.txt",
    "SETUP.md",
    "INSTALL.txt",
]

# オプションで含めるファイル（存在する場合のみ）
OPTIONAL_FILES = [
    "README.md",
]

# 除外するディレクトリ・ファイル
EXCLUDE_PATTERNS = [
    "__pycache__",
    "venv",
    "env",
    ".venv",
    "uploads",
    ".vercel",
    ".vscode",
    ".idea",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
    "test_structure.py",
    "html_edit_interactive.py",
    "suikankyo.html",
    "vercel.json",
    "api",
    "VERCEL_DEPLOY.md",
    ".packageignore",
    "package.bat",
    "package.sh",
    "create_package.py",
]


def create_package():
    """パッケージを作成する"""
    # 現在のディレクトリ
    current_dir = Path(__file__).parent
    package_dir = current_dir.parent / PACKAGE_NAME
    
    print("=" * 50)
    print("HTMLエディタ パッケージ作成")
    print("=" * 50)
    print()
    
    # 既存のパッケージディレクトリを削除
    if package_dir.exists():
        print(f"既存のパッケージディレクトリを削除中: {package_dir}")
        shutil.rmtree(package_dir)
    
    # パッケージディレクトリを作成
    print(f"パッケージディレクトリを作成中: {package_dir}")
    package_dir.mkdir(parents=True, exist_ok=True)
    
    print()
    print("必要なファイルをコピー中...")
    
    # 必須ファイルをコピー
    copied_files = []
    for filename in INCLUDE_FILES:
        src = current_dir / filename
        if src.exists():
            dst = package_dir / filename
            shutil.copy2(src, dst)
            copied_files.append(filename)
            print(f"  [OK] {filename}")
        else:
            print(f"  [NG] {filename} (見つかりません)")
    
    # オプションファイルをコピー
    for filename in OPTIONAL_FILES:
        src = current_dir / filename
        if src.exists():
            dst = package_dir / filename
            shutil.copy2(src, dst)
            copied_files.append(filename)
            print(f"  [OK] {filename} (オプション)")
    
    print()
    print("=" * 50)
    print("パッケージ作成完了！")
    print("=" * 50)
    print()
    print(f"パッケージの場所: {package_dir}")
    print()
    print("コピーしたファイル:")
    for filename in copied_files:
        print(f"  - {filename}")
    print()
    print("次の手順:")
    print(f"1. {package_dir} フォルダを他のPCにコピー")
    print("2. SETUP.md または INSTALL.txt の手順に従ってセットアップ")
    print()
    
    return package_dir


if __name__ == "__main__":
    try:
        package_dir = create_package()
        print("[OK] パッケージ作成が正常に完了しました。")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

