#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLファイル対話的編集ツール
コマンドライン引数でHTMLファイルを指定して編集できるプログラム
"""

import argparse
import sys
import io
from pathlib import Path
from bs4 import BeautifulSoup
from html_editor import HTMLEditor

# Windowsでの日本語表示対応
if sys.platform == 'win32':
    try:
        # コードページをUTF-8に変更
        import os
        os.system('chcp 65001 >nul 2>&1')
        # 標準出力のエンコーディングをUTF-8に設定
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        # エンコーディング設定に失敗した場合はそのまま続行
        pass


def print_menu():
    """メニューを表示"""
    print("\n" + "=" * 60)
    print("HTML編集メニュー")
    print("=" * 60)
    print("1. 構造情報を表示")
    print("2. IDで要素を検索・編集")
    print("3. クラスで要素を検索・編集")
    print("4. タグで要素を検索・編集")
    print("5. タイトルを編集")
    print("6. メタタグを編集")
    print("7. リンク一覧を表示")
    print("8. 画像一覧を表示")
    print("9. 要素を追加")
    print("10. 要素を削除")
    print("11. 要素を置き換え")
    print("12. 変更を保存")
    print("13. 別名で保存")
    print("0. 終了")
    print("=" * 60)


def edit_element_by_id(editor: HTMLEditor):
    """IDで要素を検索して編集"""
    element_id = input("検索するIDを入力してください: ").strip()
    if not element_id:
        print("IDが入力されていません。")
        return
    
    element = editor.find_by_id(element_id)
    if not element:
        print(f"ID '{element_id}' の要素が見つかりませんでした。")
        return
    
    print(f"\n見つかった要素: {element.name}")
    print(f"現在の内容: {element.get_text(strip=True)[:100]}")
    print(f"現在の属性: {dict(element.attrs)}")
    
    print("\n編集オプション:")
    print("1. テキストを変更")
    print("2. 属性を変更")
    print("3. HTMLコンテンツを変更")
    choice = input("選択してください (1-3): ").strip()
    
    if choice == "1":
        new_text = input("新しいテキストを入力してください: ")
        editor.update_text(element, new_text)
        print("テキストを更新しました。")
    elif choice == "2":
        attr_name = input("属性名を入力してください: ").strip()
        attr_value = input("属性値を入力してください: ").strip()
        editor.update_attribute(element, attr_name, attr_value)
        print(f"属性 '{attr_name}' を '{attr_value}' に更新しました。")
    elif choice == "3":
        new_html = input("新しいHTMLコンテンツを入力してください: ")
        element.string = ""
        element.append(BeautifulSoup(new_html, 'html.parser'))
        print("HTMLコンテンツを更新しました。")


def edit_element_by_class(editor: HTMLEditor):
    """クラスで要素を検索して編集"""
    class_name = input("検索するクラス名を入力してください: ").strip()
    if not class_name:
        print("クラス名が入力されていません。")
        return
    
    elements = editor.find_by_class(class_name)
    if not elements:
        print(f"クラス '{class_name}' の要素が見つかりませんでした。")
        return
    
    print(f"\n{len(elements)}個の要素が見つかりました:")
    for i, elem in enumerate(elements[:10], 1):  # 最初の10個のみ表示
        print(f"{i}. {elem.name} - {elem.get_text(strip=True)[:50]}")
    
    if len(elements) > 10:
        print(f"... 他 {len(elements) - 10}個の要素")
    
    try:
        index = int(input(f"編集する要素の番号を入力してください (1-{min(len(elements), 10)}): ")) - 1
        if 0 <= index < len(elements):
            element = elements[index]
            new_text = input("新しいテキストを入力してください: ")
            editor.update_text(element, new_text)
            print("テキストを更新しました。")
        else:
            print("無効な番号です。")
    except ValueError:
        print("無効な入力です。")


def edit_element_by_tag(editor: HTMLEditor):
    """タグで要素を検索して編集"""
    tag_name = input("検索するタグ名を入力してください (例: div, p, a): ").strip()
    if not tag_name:
        print("タグ名が入力されていません。")
        return
    
    elements = editor.find_by_tag(tag_name)
    if not elements:
        print(f"タグ '{tag_name}' の要素が見つかりませんでした。")
        return
    
    print(f"\n{len(elements)}個の要素が見つかりました:")
    for i, elem in enumerate(elements[:10], 1):
        text = elem.get_text(strip=True)[:50] if elem.get_text(strip=True) else "(テキストなし)"
        print(f"{i}. {elem.name} - {text}")
    
    if len(elements) > 10:
        print(f"... 他 {len(elements) - 10}個の要素")
    
    try:
        index = int(input(f"編集する要素の番号を入力してください (1-{min(len(elements), 10)}): ")) - 1
        if 0 <= index < len(elements):
            element = elements[index]
            new_text = input("新しいテキストを入力してください: ")
            editor.update_text(element, new_text)
            print("テキストを更新しました。")
        else:
            print("無効な番号です。")
    except ValueError:
        print("無効な入力です。")


def edit_title(editor: HTMLEditor):
    """タイトルを編集"""
    current_title = editor.get_title()
    print(f"現在のタイトル: {current_title}")
    new_title = input("新しいタイトルを入力してください: ").strip()
    if new_title:
        editor.set_title(new_title)
        print("タイトルを更新しました。")
    else:
        print("タイトルが入力されていません。")


def edit_meta(editor: HTMLEditor):
    """メタタグを編集"""
    meta_name = input("メタタグのnameまたはpropertyを入力してください: ").strip()
    if not meta_name:
        print("メタタグ名が入力されていません。")
        return
    
    current_value = editor.get_meta(meta_name)
    print(f"現在の値: {current_value}")
    new_value = input("新しい値を入力してください: ").strip()
    if new_value:
        editor.set_meta(meta_name, new_value)
        print("メタタグを更新しました。")
    else:
        print("値が入力されていません。")


def show_links(editor: HTMLEditor):
    """リンク一覧を表示"""
    links = editor.get_all_links()
    print(f"\nリンク数: {len(links)}")
    print("-" * 60)
    for i, link in enumerate(links[:20], 1):  # 最初の20個のみ表示
        print(f"{i}. {link['text']}")
        print(f"   URL: {link['href']}")
        if link['id']:
            print(f"   ID: {link['id']}")
        if link['class']:
            print(f"   クラス: {link['class']}")
        print()
    
    if len(links) > 20:
        print(f"... 他 {len(links) - 20}個のリンク")


def show_images(editor: HTMLEditor):
    """画像一覧を表示"""
    images = editor.get_all_images()
    print(f"\n画像数: {len(images)}")
    print("-" * 60)
    for i, img in enumerate(images, 1):
        print(f"{i}. {img['src']}")
        if img['alt']:
            print(f"   Alt: {img['alt']}")
        if img['id']:
            print(f"   ID: {img['id']}")
        if img['class']:
            print(f"   クラス: {img['class']}")
        print()


def add_element(editor: HTMLEditor):
    """要素を追加"""
    tag = input("追加するタグ名を入力してください (例: div, p, span): ").strip()
    if not tag:
        print("タグ名が入力されていません。")
        return
    
    text = input("テキスト内容を入力してください (空欄可): ").strip()
    
    print("属性を追加しますか？ (y/n): ", end="")
    if input().strip().lower() == 'y':
        attrs = {}
        while True:
            attr_name = input("属性名を入力してください (空欄で終了): ").strip()
            if not attr_name:
                break
            attr_value = input("属性値を入力してください: ").strip()
            attrs[attr_name] = attr_value
    else:
        attrs = None
    
    # 親要素を選択
    print("\n親要素を選択してください:")
    print("1. <head>")
    print("2. <body>")
    print("3. IDで指定")
    parent_choice = input("選択 (1-3): ").strip()
    
    if parent_choice == "1":
        parent = editor.soup.find('head')
    elif parent_choice == "2":
        parent = editor.soup.find('body')
    elif parent_choice == "3":
        parent_id = input("親要素のIDを入力してください: ").strip()
        parent = editor.find_by_id(parent_id)
    else:
        print("無効な選択です。")
        return
    
    if not parent:
        print("親要素が見つかりませんでした。")
        return
    
    editor.add_element(parent, tag, text if text else None, attrs)
    print(f"要素 '<{tag}>' を追加しました。")


def remove_element(editor: HTMLEditor):
    """要素を削除"""
    element_id = input("削除する要素のIDを入力してください: ").strip()
    if not element_id:
        print("IDが入力されていません。")
        return
    
    element = editor.find_by_id(element_id)
    if not element:
        print(f"ID '{element_id}' の要素が見つかりませんでした。")
        return
    
    print(f"削除する要素: {element.name} - {element.get_text(strip=True)[:50]}")
    confirm = input("本当に削除しますか？ (y/n): ").strip().lower()
    if confirm == 'y':
        editor.remove_element(element)
        print("要素を削除しました。")
    else:
        print("削除をキャンセルしました。")


def replace_element(editor: HTMLEditor):
    """要素を置き換え"""
    element_id = input("置き換える要素のIDを入力してください: ").strip()
    if not element_id:
        print("IDが入力されていません。")
        return
    
    element = editor.find_by_id(element_id)
    if not element:
        print(f"ID '{element_id}' の要素が見つかりませんでした。")
        return
    
    new_tag = input("新しいタグ名を入力してください: ").strip()
    if not new_tag:
        print("タグ名が入力されていません。")
        return
    
    new_text = input("新しいテキストを入力してください (空欄可): ").strip()
    editor.replace_element(element, new_tag, new_text if new_text else None)
    print("要素を置き換えました。")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='HTMLファイルを対話的に編集するツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python html_edit_interactive.py suikankyo.html
  python html_edit_interactive.py path/to/file.html
        """
    )
    parser.add_argument(
        'html_file',
        type=str,
        help='編集するHTMLファイルのパス'
    )
    parser.add_argument(
        '--encoding',
        type=str,
        default='utf-8',
        help='ファイルのエンコーディング (デフォルト: utf-8)'
    )
    
    args = parser.parse_args()
    
    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"エラー: ファイル '{html_path}' が見つかりません。")
        sys.exit(1)
    
    try:
        print(f"HTMLファイルを読み込み中: {html_path}")
        editor = HTMLEditor(str(html_path), encoding=args.encoding)
        print("読み込み完了！")
        
        while True:
            print_menu()
            try:
                choice = input("選択してください: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nプログラムを終了します。")
                break
            
            if not choice:
                print("選択が入力されていません。再度入力してください。")
                continue
            
            try:
                if choice == "0":
                    print("終了します。")
                    break
                elif choice == "1":
                    print("\n構造情報を取得中...", flush=True)
                    try:
                        # 構造情報を表示
                        editor.print_structure()
                        print("\n構造情報の表示が完了しました。", flush=True)
                    except Exception as e:
                        print(f"\nエラー: 構造情報の表示中に問題が発生しました: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                    # 次のメニュー表示前に少し待機
                    input("\nEnterキーを押してメニューに戻ります...")
                elif choice == "2":
                    edit_element_by_id(editor)
                elif choice == "3":
                    edit_element_by_class(editor)
                elif choice == "4":
                    edit_element_by_tag(editor)
                elif choice == "5":
                    edit_title(editor)
                elif choice == "6":
                    edit_meta(editor)
                elif choice == "7":
                    show_links(editor)
                elif choice == "8":
                    show_images(editor)
                elif choice == "9":
                    add_element(editor)
                elif choice == "10":
                    remove_element(editor)
                elif choice == "11":
                    replace_element(editor)
                elif choice == "12":
                    editor.save()
                elif choice == "13":
                    output_path = input("保存先のファイルパスを入力してください: ").strip()
                    if output_path:
                        editor.save(output_path)
                    else:
                        print("ファイルパスが入力されていません。")
                else:
                    print("無効な選択です。")
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"エラー: 必要なライブラリがインストールされていません: {e}")
        print("インストール: pip install beautifulsoup4 lxml")
        sys.exit(1)

