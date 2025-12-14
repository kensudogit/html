#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML構文解析・編集ツール
BeautifulSoupを使用してHTMLファイルを解析・編集するプログラム
"""

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from pathlib import Path
import re
from typing import Optional, List, Dict, Any, Tuple
import json
import warnings


class HTMLEditor:
    """HTMLファイルを構文解析・編集するクラス"""
    
    def __init__(self, html_file_path: str, encoding: str = 'utf-8'):
        """
        初期化
        
        Args:
            html_file_path: HTMLファイルのパス
            encoding: ファイルのエンコーディング（デフォルト: utf-8）
        """
        self.html_file_path = Path(html_file_path)
        self.encoding = encoding
        self.soup = None
        self._load_html()
    
    def _load_html(self):
        """HTMLファイルを読み込んでBeautifulSoupオブジェクトを作成"""
        if not self.html_file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {self.html_file_path}")
        
        with open(self.html_file_path, 'r', encoding=self.encoding) as f:
            content = f.read()
        
        self.soup = BeautifulSoup(content, 'html.parser')
    
    def save(self, output_path: Optional[str] = None, pretty_print: bool = True):
        """
        HTMLをファイルに保存
        
        Args:
            output_path: 出力先のパス（Noneの場合は元のファイルに上書き）
            pretty_print: 整形して出力するかどうか
        """
        if output_path is None:
            output_path = self.html_file_path
        else:
            output_path = Path(output_path)
        
        # 出力形式を設定
        if pretty_print:
            html_str = self.soup.prettify()
        else:
            html_str = str(self.soup)
        
        with open(output_path, 'w', encoding=self.encoding) as f:
            f.write(html_str)
        
        print(f"保存しました: {output_path}")
    
    def find_by_id(self, element_id: str):
        """IDで要素を検索"""
        return self.soup.find(id=element_id)
    
    def find_by_class(self, class_name: str, tag: Optional[str] = None):
        """
        クラス名で要素を検索
        
        Args:
            class_name: クラス名
            tag: タグ名（オプション）
        """
        if tag:
            return self.soup.find_all(tag, class_=class_name)
        return self.soup.find_all(class_=class_name)
    
    def find_by_tag(self, tag_name: str):
        """タグ名で要素を検索"""
        return self.soup.find_all(tag_name)
    
    def find_by_attribute(self, attr_name: str, attr_value: str):
        """属性で要素を検索"""
        return self.soup.find_all(attrs={attr_name: attr_value})
    
    def find_by_text(self, text: str, exact: bool = False):
        """
        テキストで要素を検索
        
        Args:
            text: 検索するテキスト
            exact: 完全一致かどうか
        """
        if exact:
            return self.soup.find_all(string=re.compile(f'^{re.escape(text)}$'))
        return self.soup.find_all(string=re.compile(re.escape(text)))
    
    def get_title(self) -> Optional[str]:
        """タイトルを取得"""
        title_tag = self.soup.find('title')
        return title_tag.string if title_tag else None
    
    def set_title(self, new_title: str):
        """タイトルを設定"""
        title_tag = self.soup.find('title')
        if title_tag:
            title_tag.string = new_title
        else:
            # titleタグが存在しない場合はhead内に追加
            head = self.soup.find('head')
            if head:
                head.append(self.soup.new_tag('title'))
                head.title.string = new_title
    
    def get_meta(self, name: str, attr: str = 'name') -> Optional[str]:
        """
        メタタグの値を取得
        
        Args:
            name: メタタグのnameまたはproperty
            attr: 属性名（'name' または 'property'）
        """
        meta = self.soup.find('meta', attrs={attr: name})
        return meta.get('content') if meta else None
    
    def set_meta(self, name: str, content: str, attr: str = 'name'):
        """
        メタタグを設定
        
        Args:
            name: メタタグのnameまたはproperty
            content: コンテンツ
            attr: 属性名（'name' または 'property'）
        """
        meta = self.soup.find('meta', attrs={attr: name})
        if meta:
            meta['content'] = content
        else:
            # メタタグが存在しない場合はhead内に追加
            head = self.soup.find('head')
            if head:
                new_meta = self.soup.new_tag('meta', attrs={attr: name, 'content': content})
                head.append(new_meta)
    
    def get_all_links(self) -> List[Dict[str, str]]:
        """すべてのリンク（aタグ）を取得"""
        links = []
        for a_tag in self.soup.find_all('a'):
            links.append({
                'text': a_tag.get_text(strip=True),
                'href': a_tag.get('href', ''),
                'id': a_tag.get('id', ''),
                'class': ' '.join(a_tag.get('class', []))
            })
        return links
    
    def get_all_images(self) -> List[Dict[str, str]]:
        """すべての画像（imgタグ）を取得"""
        images = []
        for img_tag in self.soup.find_all('img'):
            images.append({
                'src': img_tag.get('src', ''),
                'alt': img_tag.get('alt', ''),
                'id': img_tag.get('id', ''),
                'class': ' '.join(img_tag.get('class', []))
            })
        return images
    
    def update_text(self, element, new_text: str):
        """
        要素のテキストを更新
        
        Args:
            element: BeautifulSoupの要素オブジェクト
            new_text: 新しいテキスト
        """
        if element:
            element.string = new_text
    
    def update_attribute(self, element, attr_name: str, attr_value: str):
        """
        要素の属性を更新
        
        Args:
            element: BeautifulSoupの要素オブジェクト
            attr_name: 属性名
            attr_value: 属性値
        """
        if element:
            element[attr_name] = attr_value
    
    def add_element(self, parent, tag: str, text: Optional[str] = None, 
                   attrs: Optional[Dict[str, str]] = None):
        """
        要素を追加
        
        Args:
            parent: 親要素
            tag: タグ名
            text: テキスト内容
            attrs: 属性の辞書
        """
        new_element = self.soup.new_tag(tag)
        if text:
            new_element.string = text
        if attrs:
            for key, value in attrs.items():
                new_element[key] = value
        parent.append(new_element)
        return new_element
    
    def remove_element(self, element):
        """要素を削除"""
        if element:
            element.decompose()
    
    def replace_element(self, old_element, new_tag: str, new_text: Optional[str] = None,
                       new_attrs: Optional[Dict[str, str]] = None):
        """
        要素を置き換え
        
        Args:
            old_element: 置き換える要素
            new_tag: 新しいタグ名
            new_text: 新しいテキスト
            new_attrs: 新しい属性
        """
        if old_element:
            new_element = self.soup.new_tag(new_tag)
            if new_text:
                new_element.string = new_text
            if new_attrs:
                for key, value in new_attrs.items():
                    new_element[key] = value
            old_element.replace_with(new_element)
            return new_element
    
    def get_structure_info(self) -> Dict[str, Any]:
        """HTMLの構造情報を取得"""
        info = {
            'title': self.get_title(),
            'meta_tags': {},
            'links_count': len(self.soup.find_all('a')),
            'images_count': len(self.soup.find_all('img')),
            'scripts_count': len(self.soup.find_all('script')),
            'stylesheets_count': len(self.soup.find_all('link', rel='stylesheet')),
            'forms_count': len(self.soup.find_all('form')),
        }
        
        # メタタグ情報を取得
        for meta in self.soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            if name:
                info['meta_tags'][name] = meta.get('content', '')
        
        return info
    
    def print_structure(self):
        """HTMLの構造を表示"""
        try:
            info = self.get_structure_info()
            # 出力を即座に表示するためにflush=Trueを使用
            print("\n" + "=" * 60, flush=True)
            print("HTML構造情報", flush=True)
            print("=" * 60, flush=True)
            print(f"タイトル: {info['title'] or '(タイトルなし)'}", flush=True)
            print(f"リンク数: {info['links_count']}", flush=True)
            print(f"画像数: {info['images_count']}", flush=True)
            print(f"スクリプト数: {info['scripts_count']}", flush=True)
            print(f"スタイルシート数: {info['stylesheets_count']}", flush=True)
            print(f"フォーム数: {info['forms_count']}", flush=True)
            
            if info['meta_tags']:
                print("\nメタタグ:", flush=True)
                for name, content in info['meta_tags'].items():
                    content_str = content[:50] + "..." if len(content) > 50 else content
                    print(f"  {name}: {content_str}", flush=True)
            else:
                print("\nメタタグ: (なし)", flush=True)
            
            print("=" * 60 + "\n", flush=True)
        except Exception as e:
            print(f"エラー: 構造情報の取得中に問題が発生しました: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    def export_to_json(self, output_path: str):
        """構造情報をJSONファイルにエクスポート"""
        info = self.get_structure_info()
        info['links'] = self.get_all_links()
        info['images'] = self.get_all_images()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        
        print(f"JSONファイルを保存しました: {output_path}")
    
    def validate_html(self) -> List[Dict[str, Any]]:
        """
        HTMLの構文エラーを検証
        
        Returns:
            エラーのリスト。各エラーは {'type': str, 'message': str, 'line': int, 'column': int} の形式
        """
        errors = []
        
        try:
            # HTMLファイルの内容を取得
            with open(self.html_file_path, 'r', encoding=self.encoding) as f:
                content = f.read()
                lines = content.split('\n')
            
            # 基本的な構文チェック
            errors.extend(self._check_basic_syntax(content, lines))
            
            # BeautifulSoupでパースしてエラーを検出
            errors.extend(self._check_parsing_errors(content, lines))
            
            # タグの整合性チェック
            errors.extend(self._check_tag_consistency(content, lines))
            
            # 属性のチェック
            errors.extend(self._check_attributes(content, lines))
            
        except Exception as e:
            errors.append({
                'type': 'error',
                'message': f'検証中にエラーが発生しました: {str(e)}',
                'line': 0,
                'column': 0
            })
        
        return errors
    
    def _check_basic_syntax(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """基本的な構文チェック"""
        errors = []
        
        # DOCTYPE宣言のチェック
        if '<!DOCTYPE' not in content.upper() and '<HTML' not in content.upper():
            errors.append({
                'type': 'warning',
                'message': 'DOCTYPE宣言が見つかりません。HTML5の場合は <!DOCTYPE html> を追加することを推奨します。',
                'line': 1,
                'column': 0
            })
        
        # 属性値の引用符チェック
        for line_num, line in enumerate(lines, 1):
            # タグ内で引用符が閉じられていない場合を検出
            # タグの開始から終了までを追跡
            i = 0
            while i < len(line):
                if line[i] == '<' and (i == 0 or line[i-1] != '\\'):
                    tag_start = i
                    i += 1
                    in_tag = True
                    in_quote = False
                    quote_char = None
                    
                    while i < len(line) and in_tag:
                        char = line[i]
                        if not in_quote:
                            if char == '>':
                                in_tag = False
                            elif char in ['"', "'"]:
                                in_quote = True
                                quote_char = char
                        else:
                            if char == quote_char and (i == 0 or line[i-1] != '\\'):
                                in_quote = False
                                quote_char = None
                        i += 1
                    
                    # タグが閉じられていない、または引用符が閉じられていない
                    if in_tag or in_quote:
                        if in_quote:
                            errors.append({
                                'type': 'error',
                                'message': f'属性値の引用符が閉じられていません',
                                'line': line_num,
                                'column': tag_start
                            })
                        elif in_tag:
                            errors.append({
                                'type': 'error',
                                'message': f'タグが正しく閉じられていません（引用符が閉じられていない可能性があります）',
                                'line': line_num,
                                'column': tag_start
                            })
                else:
                    i += 1
        
        # 閉じタグの基本的なチェック
        open_tags = []
        tag_pattern = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>')
        
        for line_num, line in enumerate(lines, 1):
            for match in tag_pattern.finditer(line):
                is_closing = match.group(1) == '/'
                tag_name = match.group(2).lower()
                
                # 自己完結型タグはスキップ
                if tag_name in ['br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr']:
                    continue
                
                if is_closing:
                    if not open_tags or open_tags[-1] != tag_name:
                        if tag_name in open_tags:
                            errors.append({
                                'type': 'error',
                                'message': f'閉じタグの順序が不正です: </{tag_name}>',
                                'line': line_num,
                                'column': match.start()
                            })
                        else:
                            errors.append({
                                'type': 'error',
                                'message': f'対応する開始タグが見つかりません: </{tag_name}>',
                                'line': line_num,
                                'column': match.start()
                            })
                    else:
                        open_tags.pop()
                else:
                    open_tags.append(tag_name)
        
        # 閉じられていないタグをチェック
        for tag in open_tags:
            errors.append({
                'type': 'error',
                'message': f'閉じタグが見つかりません: <{tag}>',
                'line': len(lines),
                'column': 0
            })
        
        return errors
    
    def _check_parsing_errors(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """BeautifulSoupでのパースエラーをチェック"""
        errors = []
        
        # まずhtml.parserでチェック
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                soup = BeautifulSoup(content, 'html.parser')
                
                # 警告をエラーとして記録
                for warning in w:
                    if issubclass(warning.category, UserWarning):
                        # 行番号を推定
                        line_num = 1
                        if hasattr(warning, 'lineno'):
                            line_num = warning.lineno
                        else:
                            # メッセージから行番号を抽出を試みる
                            msg = str(warning.message)
                            match = re.search(r'line\s+(\d+)', msg, re.IGNORECASE)
                            if match:
                                line_num = int(match.group(1))
                        
                        errors.append({
                            'type': 'warning',
                            'message': str(warning.message),
                            'line': line_num,
                            'column': 0
                        })
        except Exception as e:
            errors.append({
                'type': 'error',
                'message': f'HTMLのパースに失敗しました: {str(e)}',
                'line': 1,
                'column': 0
            })
        
        # lxmlパーサーが利用可能な場合は、より厳密なチェックを実行
        try:
            from lxml import etree
            from lxml.html import HTMLParser
            
            parser = HTMLParser(recover=False, encoding='utf-8')
            try:
                etree.fromstring(content.encode('utf-8'), parser=parser)
            except etree.XMLSyntaxError as e:
                # lxmlのエラーメッセージから行番号を取得
                line_num = getattr(e, 'lineno', 1)
                column = getattr(e, 'offset', 0)
                errors.append({
                    'type': 'error',
                    'message': f'XML構文エラー: {str(e)}',
                    'line': line_num,
                    'column': column
                })
        except ImportError:
            # lxmlがインストールされていない場合はスキップ
            pass
        except Exception as e:
            # lxmlでのチェック中にエラーが発生した場合は無視（html.parserの結果を優先）
            pass
        
        return errors
    
    def _check_tag_consistency(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """タグの整合性をチェック"""
        errors = []
        
        # html, head, bodyタグのチェック
        has_html = re.search(r'<html[^>]*>', content, re.IGNORECASE)
        has_head = re.search(r'<head[^>]*>', content, re.IGNORECASE)
        has_body = re.search(r'<body[^>]*>', content, re.IGNORECASE)
        
        if has_html and not has_head:
            errors.append({
                'type': 'warning',
                'message': '<html>タグがありますが、<head>タグが見つかりません。',
                'line': 1,
                'column': 0
            })
        
        if has_html and not has_body:
            errors.append({
                'type': 'warning',
                'message': '<html>タグがありますが、<body>タグが見つかりません。',
                'line': 1,
                'column': 0
            })
        
        # titleタグのチェック（head内にあるべき）
        if has_head:
            head_end = content.find('</head>', content.find('<head'))
            if head_end > 0:
                head_content = content[content.find('<head'):head_end]
                if '<title' not in head_content.lower():
                    errors.append({
                        'type': 'warning',
                        'message': '<head>タグ内に<title>タグが見つかりません。SEOのため追加することを推奨します。',
                        'line': 1,
                        'column': 0
                    })
        
        return errors
    
    def _check_attributes(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """属性のチェック"""
        errors = []
        
        # imgタグのalt属性チェック
        img_pattern = re.compile(r'<img[^>]*>', re.IGNORECASE)
        for line_num, line in enumerate(lines, 1):
            for match in img_pattern.finditer(line):
                img_tag = match.group(0)
                if 'alt=' not in img_tag.lower():
                    errors.append({
                        'type': 'warning',
                        'message': '<img>タグにalt属性がありません。アクセシビリティのため追加することを推奨します。',
                        'line': line_num,
                        'column': match.start()
                    })
        
        # aタグのhref属性チェック
        a_pattern = re.compile(r'<a[^>]*>', re.IGNORECASE)
        for line_num, line in enumerate(lines, 1):
            for match in a_pattern.finditer(line):
                a_tag = match.group(0)
                if 'href=' not in a_tag.lower() and 'name=' not in a_tag.lower():
                    errors.append({
                        'type': 'warning',
                        'message': '<a>タグにhref属性またはname属性がありません。',
                        'line': line_num,
                        'column': match.start()
                    })
        
        return errors


def main():
    """使用例"""
    # HTMLファイルのパス
    html_file = r"C:\devlop\html\suikankyo.html"
    
    try:
        # HTMLEditorインスタンスを作成
        editor = HTMLEditor(html_file)
        
        # 構造情報を表示
        editor.print_structure()
        
        # タイトルを取得
        print(f"\n現在のタイトル: {editor.get_title()}")
        
        # メタタグを取得
        csrf_token = editor.get_meta('csrf-token')
        print(f"CSRF Token: {csrf_token}")
        
        # IDで要素を検索
        path_name = editor.find_by_id('path_name')
        if path_name:
            print(f"path_name要素の値: {path_name.get('value')}")
        
        # クラスで要素を検索
        menu_items = editor.find_by_class('index_class')
        print(f"\nindex_classクラスの要素数: {len(menu_items)}")
        
        # リンク一覧を取得（最初の5つ）
        links = editor.get_all_links()
        print(f"\nリンク数: {len(links)}")
        print("最初の5つのリンク:")
        for i, link in enumerate(links[:5], 1):
            print(f"  {i}. {link['text']} -> {link['href']}")
        
        # 編集例（コメントアウト）
        # editor.set_title("新しいタイトル")
        # editor.save(output_path=r"C:\devlop\html\suikankyo_edited.html")
        
        # JSONにエクスポート
        # editor.export_to_json(r"C:\devlop\html\structure_info.json")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

