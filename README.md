# HTML構文解析・編集ツール

HTMLファイルを構文解析して編集するためのPythonプログラムです。

## 必要なライブラリ

```bash
pip install -r requirements.txt
```

## 使い方

### 基本的な使用例

```python
from html_editor import HTMLEditor

# HTMLファイルを読み込む
editor = HTMLEditor("suikankyo.html")

# 構造情報を表示
editor.print_structure()

# タイトルを取得
title = editor.get_title()
print(f"タイトル: {title}")

# タイトルを変更
editor.set_title("新しいタイトル")

# メタタグを取得
csrf_token = editor.get_meta('csrf-token')
print(f"CSRF Token: {csrf_token}")

# メタタグを設定
editor.set_meta('description', '新しい説明文')

# IDで要素を検索
element = editor.find_by_id('path_name')
if element:
    print(f"値: {element.get('value')}")

# クラスで要素を検索
elements = editor.find_by_class('index_class')

# タグで要素を検索
links = editor.find_by_tag('a')

# すべてのリンクを取得
all_links = editor.get_all_links()
for link in all_links:
    print(f"{link['text']} -> {link['href']}")

# 要素のテキストを更新
element = editor.find_by_id('some_id')
if element:
    editor.update_text(element, "新しいテキスト")

# 要素の属性を更新
element = editor.find_by_id('some_id')
if element:
    editor.update_attribute(element, 'class', 'new-class')

# 新しい要素を追加
head = editor.soup.find('head')
if head:
    editor.add_element(head, 'meta', attrs={'name': 'author', 'content': 'Your Name'})

# 要素を削除
element = editor.find_by_id('unwanted_id')
if element:
    editor.remove_element(element)

# 編集したHTMLを保存
editor.save()  # 元のファイルに上書き
# または
editor.save("output.html")  # 新しいファイルに保存

# 構造情報をJSONにエクスポート
editor.export_to_json("structure_info.json")
```

## 主な機能

### 検索機能
- `find_by_id(element_id)`: IDで要素を検索
- `find_by_class(class_name, tag=None)`: クラス名で要素を検索
- `find_by_tag(tag_name)`: タグ名で要素を検索
- `find_by_attribute(attr_name, attr_value)`: 属性で要素を検索
- `find_by_text(text, exact=False)`: テキストで要素を検索

### 取得機能
- `get_title()`: タイトルを取得
- `get_meta(name, attr='name')`: メタタグの値を取得
- `get_all_links()`: すべてのリンクを取得
- `get_all_images()`: すべての画像を取得
- `get_structure_info()`: HTMLの構造情報を取得

### 編集機能
- `set_title(new_title)`: タイトルを設定
- `set_meta(name, content, attr='name')`: メタタグを設定
- `update_text(element, new_text)`: 要素のテキストを更新
- `update_attribute(element, attr_name, attr_value)`: 要素の属性を更新
- `add_element(parent, tag, text=None, attrs=None)`: 要素を追加
- `remove_element(element)`: 要素を削除
- `replace_element(old_element, new_tag, new_text=None, new_attrs=None)`: 要素を置き換え

### 保存・エクスポート機能
- `save(output_path=None, pretty_print=True)`: HTMLをファイルに保存
- `export_to_json(output_path)`: 構造情報をJSONファイルにエクスポート
- `print_structure()`: HTMLの構造を表示

## 実行方法

### 1. 基本的な実行（html_editor.py）

```bash
python html_editor.py
```

実行すると、`suikankyo.html`の構造情報が表示されます。

### 2. 対話的編集ツール（html_edit_interactive.py）

コマンドライン引数でHTMLファイルを指定して、対話的に編集できます。

```bash
# 基本的な使い方
python html_edit_interactive.py suikankyo.html

# エンコーディングを指定
python html_edit_interactive.py suikankyo.html --encoding utf-8

# 別のファイルを編集
python html_edit_interactive.py path/to/your/file.html
```

#### 対話的編集ツールの機能

1. **構造情報を表示** - HTMLファイルの構造情報を表示
2. **IDで要素を検索・編集** - IDを指定して要素を検索し、テキストや属性を編集
3. **クラスで要素を検索・編集** - クラス名で要素を検索して編集
4. **タグで要素を検索・編集** - タグ名で要素を検索して編集
5. **タイトルを編集** - HTMLのタイトルを変更
6. **メタタグを編集** - メタタグの値を変更
7. **リンク一覧を表示** - すべてのリンクを一覧表示
8. **画像一覧を表示** - すべての画像を一覧表示
9. **要素を追加** - 新しい要素を追加
10. **要素を削除** - 指定したIDの要素を削除
11. **要素を置き換え** - 要素を別のタグに置き換え
12. **変更を保存** - 元のファイルに上書き保存
13. **別名で保存** - 別のファイル名で保存

#### 使用例

```bash
# HTMLファイルを指定して起動
python html_edit_interactive.py suikankyo.html

# メニューから操作を選択
# 例: 1を選択して構造情報を表示
# 例: 5を選択してタイトルを編集
# 例: 12を選択して変更を保存
```

### 3. Webベースエディタ（web_html_editor.py）

ブラウザ上でHTMLファイルを編集できるWebアプリケーションです。ファイルをアップロードして編集することもできます。

```bash
# ファイルを指定せずに起動（ブラウザからアップロード可能）
python web_html_editor.py

# ファイルを指定して起動（デフォルト: http://127.0.0.1:5000）
python web_html_editor.py suikankyo.html

# ポート番号を指定
python web_html_editor.py suikankyo.html --port 8080

# すべてのネットワークインターフェースで公開
python web_html_editor.py suikankyo.html --host 0.0.0.0 --port 8080

# デバッグモードで起動
python web_html_editor.py suikankyo.html --debug
```

#### Webエディタの機能

- **ファイルアップロード** - ブラウザからHTMLファイルをアップロードして編集
- **ファイル一覧** - アップロードされたファイルの一覧を表示・選択
- **ファイルダウンロード** - 編集したファイルをダウンロード
- **リアルタイムプレビュー** - 編集内容が即座にプレビューに反映されます
- **保存機能** - 編集した内容をファイルに保存（Ctrl+Sでも保存可能）
- **再読み込み** - ファイルを再読み込みして最新の状態に戻す
- **構造情報表示** - HTMLファイルの構造情報を表示
- **検索機能** - ID、クラス、タグで要素を検索
- **検索・置換** - 文字列の検索と置換
- **ファイル情報** - ファイルサイズ、リンク数、画像数などの情報を表示

#### 使用例

```bash
# 1. Webサーバーを起動（ファイルを指定しない場合）
python web_html_editor.py

# または、ファイルを指定して起動
python web_html_editor.py suikankyo.html

# 2. ブラウザで http://127.0.0.1:5000 を開く

# 3. ファイルをアップロード（ファイルを指定しなかった場合）
#    - 「ファイルをアップロード」ボタンをクリック
#    - HTMLファイルを選択してアップロード

# 4. エディタでHTMLを編集

# 5. 「保存」ボタンをクリック（またはCtrl+S）で保存

# 6. プレビューで編集結果を確認

# 7. 「ダウンロード」ボタンで編集したファイルをダウンロード
```

#### ファイル管理機能

- **アップロード**: 「ファイルをアップロード」ボタンからHTMLファイルをアップロード
- **ファイル一覧**: 「ファイル一覧」ボタンでアップロードされたファイルを確認
- **ファイル選択**: ファイル一覧から「開く」ボタンでファイルを選択して編集
- **ファイル削除**: ファイル一覧から「削除」ボタンでファイルを削除
- **ダウンロード**: 編集したファイルを「ダウンロード」ボタンでダウンロード

**注意**: アップロードされたファイルは `uploads/` フォルダに保存されます。

"# html" 
