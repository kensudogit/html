#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""構造情報表示のテストスクリプト"""

# このファイルは、`HTMLEditor` の構造解析機能が正しく動くかを手動で確認するための簡易テストです。
# `suikankyo.html` を対象に、タイトル/リンク数/画像数などを出力します。

import sys
import io

# Windowsでの日本語表示対応
if sys.platform == 'win32':
    try:
        import os
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from html_editor import HTMLEditor

def main():
    print("=" * 60)
    print("構造情報表示テスト")
    print("=" * 60)
    
    try:
        print("\n1. HTMLEditorインスタンスを作成中...")
        editor = HTMLEditor("suikankyo.html")
        print("   ✓ 作成完了")
        
        print("\n2. print_structure()を呼び出し中...")
        editor.print_structure()
        print("   ✓ 呼び出し完了")
        
        print("\n3. 構造情報を直接取得中...")
        info = editor.get_structure_info()
        print(f"   ✓ タイトル: {info['title']}")
        print(f"   ✓ リンク数: {info['links_count']}")
        print(f"   ✓ 画像数: {info['images_count']}")
        print(f"   ✓ スクリプト数: {info['scripts_count']}")
        
        print("\n" + "=" * 60)
        print("テスト完了: すべて正常に動作しています")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()


