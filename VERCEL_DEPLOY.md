# Vercelへのデプロイ手順

このHTMLエディタをVercelに完全公開モードでデプロイする手順です。

## 前提条件

1. Vercelアカウント（[vercel.com](https://vercel.com)で無料登録可能）
2. Vercel CLI（オプション、コマンドラインからデプロイする場合）

## デプロイ方法

### 方法1: Vercel CLIを使用（推奨）

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

4. **デプロイ実行**
   ```bash
   vercel --prod
   ```
   
   初回デプロイ時は、いくつかの質問に答えます：
   - Set up and deploy? → **Y**
   - Which scope? → あなたのアカウントを選択
   - Link to existing project? → **N**（新規プロジェクトの場合）
   - What's your project's name? → プロジェクト名を入力（例: `html-editor`）
   - In which directory is your code located? → **./**（そのままEnter）

5. **デプロイ完了後、URLが表示されます**
   例: `https://html-editor.vercel.app`

### 方法2: GitHubリポジトリ経由

1. **GitHubにリポジトリを作成**
   - このプロジェクトをGitHubにプッシュ

2. **Vercelダッシュボードでインポート**
   - [vercel.com/dashboard](https://vercel.com/dashboard)にアクセス
   - 「Add New Project」をクリック
   - GitHubリポジトリを選択
   - プロジェクト設定：
     - Framework Preset: **Other**
     - Root Directory: **./**（そのまま）
     - Build Command: （空欄のまま）
     - Output Directory: （空欄のまま）
   - 「Deploy」をクリック

### 方法3: Vercelダッシュボードから直接アップロード

1. [vercel.com/dashboard](https://vercel.com/dashboard)にアクセス
2. 「Add New Project」をクリック
3. 「Browse」をクリックして、`C:\devlop\html`フォルダを選択
4. プロジェクト設定を入力して「Deploy」をクリック

## デプロイ後の確認

デプロイが完了したら、以下のURLにアクセスして動作を確認してください：

- メインページ: `https://your-project.vercel.app`
- ファイルアップロード機能が正常に動作するか確認
- ダウンロード機能が正常に動作するか確認

## 注意事項

1. **ファイルストレージ**: Vercelのサーバーレス環境では、`/tmp`ディレクトリを使用しています。アップロードされたファイルは一時的なもので、関数の実行が終了すると削除される可能性があります。永続的なストレージが必要な場合は、Vercel Blob Storageや外部ストレージサービス（AWS S3、Google Cloud Storageなど）の使用を検討してください。

2. **環境変数**: 必要に応じて、Vercelダッシュボードの「Settings」→「Environment Variables」から環境変数を設定できます。

3. **カスタムドメイン**: Vercelダッシュボードの「Settings」→「Domains」からカスタムドメインを設定できます。

## トラブルシューティング

### デプロイエラーが発生する場合

1. **ログを確認**: Vercelダッシュボードの「Deployments」タブでログを確認
2. **依存関係の確認**: `requirements.txt`に必要なパッケージがすべて含まれているか確認
3. **Pythonバージョン**: Vercelは自動的にPython 3.9を使用します

### アップロード機能が動作しない場合

- `/tmp`ディレクトリの権限を確認
- ファイルサイズ制限（50MB）を超えていないか確認

## 更新方法

コードを更新した後、再度デプロイを実行：

```bash
vercel --prod
```

または、GitHubリポジトリと連携している場合は、`git push`するだけで自動的に再デプロイされます。

