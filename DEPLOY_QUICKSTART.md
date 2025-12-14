# デプロイ クイックスタート

## Vercelへのデプロイ（5分）

### 1. Vercel CLIをインストール
```bash
npm install -g vercel
```

### 2. デプロイ
```bash
cd C:\devlop\html
vercel login
vercel --prod
```

### 3. 完了！
デプロイされたURLが表示されます。

---

## Railwayへのデプロイ（5分）

### 1. GitHubにプッシュ
```bash
cd C:\devlop\html
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Railwayでデプロイ
1. [railway.app](https://railway.app)にアクセス
2. "New Project" → "Deploy from GitHub repo"
3. リポジトリを選択
4. 自動的にデプロイが開始されます

### 3. 完了！
デプロイされたURLが表示されます。

---

## 必要なファイル

### Vercel用
- ✅ `vercel.json` - ルーティング設定
- ✅ `api/index.py` - エントリーポイント
- ✅ `requirements.txt` - 依存関係

### Railway用
- ✅ `Procfile` - 起動コマンド
- ✅ `runtime.txt` - Pythonバージョン
- ✅ `railway.json` - Railway設定（オプション）
- ✅ `requirements.txt` - 依存関係

---

詳細な手順は `DEPLOY.md` を参照してください。

