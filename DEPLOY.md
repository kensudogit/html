# デプロイガイド

このドキュメントでは、HTMLエディタをVercelとRailwayにデプロイする方法を説明します。

## 目次

1. [Vercelへのデプロイ](#vercelへのデプロイ)
2. [Railwayへのデプロイ](#railwayへのデプロイ)
3. [トラブルシューティング](#トラブルシューティング)

---

## Vercelへのデプロイ

### 前提条件

- Vercelアカウント（[vercel.com](https://vercel.com)で無料登録可能）
- Vercel CLI（オプション、コマンドラインからデプロイする場合）

### デプロイ手順

#### 方法1: Vercel CLIを使用（推奨）

1. **Vercel CLIをインストール**
   ```bash
   npm install -g vercel
   ```

2. **プロジェクトディレクトリに移動**
   ```bash
   cd C:\devlop\html
   ```

3. **Vercelにログイン**
   ```bash
   vercel login
   ```

4. **デプロイ**
   ```bash
   # プレビューデプロイ
   vercel
   
   # 本番デプロイ
   vercel --prod
   ```

#### 方法2: GitHub連携を使用

1. **GitHubリポジトリにプッシュ**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Vercelでプロジェクトをインポート**
   - [Vercel Dashboard](https://vercel.com/dashboard)にアクセス
   - "Add New..." → "Project"をクリック
   - GitHubリポジトリを選択
   - プロジェクト設定：
     - **Framework Preset**: Other
     - **Root Directory**: `./`
     - **Build Command**: （空欄のまま）
     - **Output Directory**: （空欄のまま）
   - "Deploy"をクリック

### Vercel設定ファイル

プロジェクトには以下の設定ファイルが含まれています：

- **`vercel.json`**: Vercelのルーティング設定
- **`api/index.py`**: Vercel用のエントリーポイント

### 重要な注意事項

- Vercelはサーバーレス環境のため、`/tmp`ディレクトリのみ書き込み可能です
- アップロードされたファイルは一時的なもので、再デプロイ時に削除される可能性があります
- ファイルの永続化が必要な場合は、外部ストレージ（S3、Cloudinaryなど）の使用を検討してください

---

## Railwayへのデプロイ

### 前提条件

- Railwayアカウント（[railway.app](https://railway.app)で無料登録可能）
- GitHubアカウント（Railwayと連携する場合）

### デプロイ手順

#### 方法1: GitHub連携を使用（推奨）

1. **GitHubリポジトリにプッシュ**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Railwayでプロジェクトを作成**
   - [Railway Dashboard](https://railway.app/dashboard)にアクセス
   - "New Project"をクリック
   - "Deploy from GitHub repo"を選択
   - GitHubリポジトリを選択

3. **環境変数の設定（オプション）**
   - プロジェクト設定 → "Variables"タブ
   - 必要に応じて環境変数を追加：
     - `PORT`: ポート番号（Railwayが自動設定）
     - `FLASK_ENV`: `production`（本番環境の場合）

4. **デプロイの確認**
   - Railwayが自動的にビルドとデプロイを開始
   - デプロイが完了すると、URLが表示されます

#### 方法2: Railway CLIを使用

1. **Railway CLIをインストール**
   ```bash
   npm install -g @railway/cli
   ```

2. **Railwayにログイン**
   ```bash
   railway login
   ```

3. **プロジェクトを初期化**
   ```bash
   cd C:\devlop\html
   railway init
   ```

4. **デプロイ**
   ```bash
   railway up
   ```

### Railway設定ファイル

プロジェクトには以下の設定ファイルが含まれています：

- **`Procfile`**: アプリケーションの起動コマンド
- **`runtime.txt`**: Pythonのバージョン指定
- **`railway.json`**: Railwayの設定（オプション）

### 重要な注意事項

- Railwayは自動的に`PORT`環境変数を設定します
- アップロードされたファイルは永続化されますが、再デプロイ時に削除される可能性があります
- ファイルの永続化が必要な場合は、RailwayのVolume機能または外部ストレージの使用を検討してください

---

## トラブルシューティング

### Vercelでの問題

#### エラー: `TypeError: issubclass() arg 1 must be a class`

**原因**: VercelのPythonランタイムが`handler`を正しく認識していない

**解決方法**:
1. `api/index.py`の`handler`関数が正しく定義されているか確認
2. `vercel.json`の設定を確認
3. 再デプロイを試す

#### エラー: `ImportError`

**原因**: 依存関係が正しくインストールされていない

**解決方法**:
1. `requirements.txt`にすべての依存関係が含まれているか確認
2. Vercelのビルドログを確認
3. 必要に応じて`vercel.json`に`builds`セクションを追加

### Railwayでの問題

#### エラー: `Port already in use`

**原因**: ポート番号の設定が正しくない

**解決方法**:
1. `Procfile`が正しく設定されているか確認
2. Railwayが自動的に設定する`PORT`環境変数を使用しているか確認
3. `web_html_editor.py`が環境変数`PORT`を読み取っているか確認

#### エラー: `Module not found`

**原因**: 依存関係が正しくインストールされていない

**解決方法**:
1. `requirements.txt`にすべての依存関係が含まれているか確認
2. Railwayのビルドログを確認
3. `runtime.txt`でPythonのバージョンを確認

### 一般的な問題

#### アップロードされたファイルが保存されない

**原因**: サーバーレス環境ではファイルシステムが永続化されない

**解決方法**:
- Vercel: `/tmp`ディレクトリを使用（一時的）
- Railway: Volume機能を使用するか、外部ストレージ（S3など）を使用

#### アプリケーションが起動しない

**解決方法**:
1. ログを確認（Vercel: Functions タブ、Railway: Deployments タブ）
2. 環境変数が正しく設定されているか確認
3. `requirements.txt`の依存関係を確認

---

## デプロイ後の確認事項

1. **アプリケーションが正常に起動しているか**
   - デプロイされたURLにアクセスして確認

2. **ファイルアップロード機能が動作するか**
   - テスト用のHTMLファイルをアップロードして確認

3. **エディタ機能が動作するか**
   - HTMLの編集とプレビューが正常に動作するか確認

4. **ダウンロード機能が動作するか**
   - 編集したファイルをダウンロードして確認

---

## 参考リンク

- [Vercel Documentation](https://vercel.com/docs)
- [Railway Documentation](https://docs.railway.app)
- [Flask Documentation](https://flask.palletsprojects.com/)

---

## サポート

問題が解決しない場合は、以下の情報を含めてサポートに問い合わせてください：

- デプロイ先（Vercel / Railway）
- エラーメッセージ
- ビルドログ
- 環境変数の設定

