# HTML Editor Frontend

React + TypeScriptで構築されたHTMLエディタのフロントエンドアプリケーション。

## 機能

- 最大27大学の入学手続き画面を比較・編集
- 複数画面の並列表示（グリッド、横並び、縦並び）
- 画面構成の比較分析
- 個別編集機能
- エラーハンドリングとローディング状態の管理
- レスポンシブデザイン対応

## セットアップ

### 依存関係のインストール

```bash
npm install
```

### 環境変数の設定

`.env`ファイルを作成して以下を設定：

```env
VITE_API_URL=http://localhost:5000
```

開発環境ではデフォルトで`http://localhost:5000`が使用されます。

## 開発サーバー起動

```bash
npm run dev
```

フロントエンドは `http://localhost:3000` で起動します。

## ビルド

```bash
npm run build
```

ビルド結果は`dist`ディレクトリに出力されます。

## プロジェクト構成

```
src/
├── components/          # Reactコンポーネント
│   ├── ScreenComparison.tsx      # メインの画面比較コンポーネント
│   ├── ComparisonFileList.tsx    # ファイルリストコンポーネント
│   ├── ComparisonGrid.tsx         # グリッド表示コンポーネント
│   ├── ComparisonScreen.tsx       # 個別画面表示コンポーネント
│   ├── ErrorBoundary.tsx          # エラーバウンダリー
│   ├── ErrorMessage.tsx           # エラーメッセージ表示
│   └── LoadingSpinner.tsx         # ローディングスピナー
├── config/              # 設定ファイル
│   └── env.ts           # 環境変数管理
├── services/            # サービス層
│   └── api.ts           # API通信サービス
├── types/               # TypeScript型定義
│   └── index.ts         # 共通型定義
├── App.tsx              # メインアプリコンポーネント
└── main.tsx             # エントリーポイント
```

## 技術スタック

- **React 18**: UIライブラリ
- **TypeScript**: 型安全性
- **Vite**: ビルドツール
- **Axios**: HTTP通信

## 主な機能

### 1. 画面比較
- 最大27大学のHTMLファイルを同時に読み込み
- グリッド、横並び、縦並びの3つのレイアウトモード
- 比較モードと編集モードの切り替え

### 2. エラーハンドリング
- ErrorBoundaryによるグローバルエラーキャッチ
- 個別のエラーメッセージ表示
- API通信エラーの適切な処理

### 3. 型安全性
- TypeScriptによる厳密な型定義
- APIレスポンスの型安全性
- 環境変数の型定義

### 4. レスポンシブデザイン
- モバイル、タブレット、デスクトップ対応
- 画面サイズに応じたレイアウト調整

## 開発ガイドライン

### コンポーネント作成
- 関数コンポーネントを使用
- TypeScriptの型定義を必ず記述
- Propsインターフェースを定義

### API通信
- `services/api.ts`の`apiService`を使用
- エラーハンドリングを適切に実装
- ローディング状態を管理

### スタイリング
- CSS Modulesまたは通常のCSSファイルを使用
- レスポンシブデザインを考慮
- アクセシビリティに配慮

## トラブルシューティング

### API接続エラー
- `.env`ファイルの`VITE_API_URL`を確認
- バックエンドサーバーが起動しているか確認
- CORS設定を確認

### ビルドエラー
- TypeScriptの型エラーを確認
- 依存関係が正しくインストールされているか確認
