# HTMLエディタ セットアップガイド

このパッケージは、WebベースのHTMLエディタです。他のPCにコピーして使用できます。

## 必要な環境

- Python 3.7以上
- pip（Pythonパッケージマネージャー）

## セットアップ手順

### 1. パッケージのコピー

以下のファイルとフォルダを他のPCにコピーしてください：

```
html/
├── web_html_editor.py    # メインアプリケーション
├── html_editor.py        # HTMLエディタクラス
├── requirements.txt      # 依存関係
├── SETUP.md             # このファイル
└── README.md            # プロジェクト説明（オプション）
```

### 2. 仮想環境の作成（推奨）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. アプリケーションの起動

```bash
# Windows
python web_html_editor.py

# macOS/Linux
python3 web_html_editor.py
```

### 5. ブラウザでアクセス

ブラウザで以下のURLにアクセスしてください：

```
http://localhost:5000
```

## 使用方法

1. **HTMLファイルのアップロード**
   - 「Upload File」ボタンをクリック
   - HTMLファイルを選択してアップロード

2. **HTMLの編集**
   - エディタでHTMLソースを編集
   - リアルタイムでプレビューが更新されます

3. **編集済みファイルのダウンロード**
   - 「Download」ボタンをクリック
   - 編集済みのHTMLファイルがダウンロードされます

4. **構文チェック**
   - 「Validate」ボタンをクリック
   - HTMLの構文エラーや警告が表示されます

## トラブルシューティング

### ポート5000が既に使用されている場合

`web_html_editor.py`を編集して、別のポートを指定してください：

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)  # ポートを5001に変更
```

### 依存関係のインストールエラー

```bash
# pipを最新版にアップグレード
python -m pip install --upgrade pip

# 再度インストール
pip install -r requirements.txt
```

### モジュールが見つからないエラー

仮想環境が有効になっているか確認してください：

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

## ファイル構成

- `web_html_editor.py`: Flaskアプリケーションのメインファイル
- `html_editor.py`: HTML解析・編集機能を提供するクラス
- `requirements.txt`: 必要なPythonパッケージのリスト

## ライセンス

このプロジェクトは自由に使用・改変できます。

