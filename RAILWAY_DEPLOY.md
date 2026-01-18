# Railway デプロイガイド（Django版）

## 前提条件

- Railwayアカウント（[railway.app](https://railway.app)で無料登録可能）
- GitHubアカウント（Railwayと連携する場合）

## デプロイ手順

### 1. Railwayでプロジェクトを作成

1. [Railway Dashboard](https://railway.app/dashboard)にアクセス
2. 「New Project」をクリック
3. 「Deploy from GitHub repo」を選択
4. リポジトリを選択

### 2. 環境変数の設定

Railwayのダッシュボードで以下の環境変数を設定：

| 環境変数 | 値 | 説明 |
|---------|-----|------|
| `SECRET_KEY` | （自動生成） | Djangoのセッション暗号化キー（自動生成される） |
| `DEBUG` | `False` | 本番環境では`False`に設定 |
| `PORT` | （自動設定） | Railwayが自動的に設定 |

**注意**: `SECRET_KEY`は設定しなくても、Djangoが自動生成しますが、本番環境では明示的に設定することを推奨します。

### 3. ビルドとデプロイ

Railwayが自動的に以下を実行します：

1. **フロントエンドのビルド**: `npm run build`
2. **Python依存関係のインストール**: `pip install -r requirements.txt`
3. **Djangoマイグレーション**: `python manage.py migrate`
4. **静的ファイルの収集**: `python manage.py collectstatic`
5. **Gunicornで起動**: `gunicorn html_editor.wsgi:application`

### 4. デプロイ後の確認

デプロイが完了したら、以下のURLにアクセス：
- Railwayが提供するURL（例: `https://your-app.railway.app`）

## 設定ファイル

### Procfile
```
web: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --access-logfile - --error-logfile - --log-level info html_editor.wsgi:application
```

### nixpacks.toml
- Python 3.12を使用
- Node.js 18を使用
- ビルド時に自動的にマイグレーションと静的ファイル収集を実行

## トラブルシューティング

### 1. マイグレーションエラー

ログでマイグレーションエラーが発生している場合：
- Railwayのダッシュボードで「Deploy Logs」を確認
- データベースが正しく初期化されているか確認

### 2. 静的ファイルが見つからない

- `collectstatic`が実行されているか確認
- `STATIC_ROOT`が正しく設定されているか確認

### 3. 500エラー

- `DEBUG=False`の場合、詳細なエラー情報は表示されません
- Railwayのログを確認してエラー内容を特定

### 4. データベースエラー

- SQLiteデータベースは永続化されない可能性があります
- RailwayのVolume機能を使用するか、PostgreSQLなどの外部データベースを使用することを推奨

## 本番環境の推奨設定

1. **データベース**: PostgreSQLなどの外部データベースを使用
2. **静的ファイル**: CDN（Cloudflare、AWS S3など）を使用
3. **ログ**: Railwayのログ機能を使用
4. **モニタリング**: Railwayのメトリクス機能を使用

## 参考リンク

- [Railway Documentation](https://docs.railway.app)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
