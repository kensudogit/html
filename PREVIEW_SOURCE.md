# プレビューとHTMLソースの関係

## 概要

**はい、プレビューに表示されている内容は、エディタに入力されているHTMLソースから生成されています。**

プレビューは、エディタ（textarea）に入力されたHTMLソースコードを取得し、それを実際のWebページとして表示します。

## 処理の流れ

### 1. HTMLソースの取得
```javascript
const editor = getEditor();  // エディタ要素を取得
let content = editor.value;  // エディタに入力されているHTMLソースを取得
```

### 2. CSS読み込みの修正（自動処理）
```javascript
// rel="preload" を rel="stylesheet" に変換
content = content.replace(
    /<link\s+rel=["']preload["']\s+href=["']([^"']+)["']\s+as=["']style["']\s+onload=["']([^"']*)["']/gi,
    '<link rel="stylesheet" href="$1"'
);
```

**この修正により：**
- `rel="preload"`を使用した遅延読み込みのCSSが、通常の`rel="stylesheet"`に変換されます
- Blob URLのコンテキストでもCSSが正しく読み込まれるようになります

### 3. Blobオブジェクトの作成
```javascript
const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
```

### 4. Blob URLの生成
```javascript
const url = URL.createObjectURL(blob);
```

### 5. iframeへの設定
```javascript
preview.src = url;  // iframeのsrcにBlob URLを設定
```

## 重要なポイント

### ✅ プレビューはHTMLソースから生成される

- エディタに入力されたHTMLソースがそのまま使用されます
- サーバーサイドでの処理は行われません（クライアントサイドのみ）
- リアルタイムで更新されます（エディタの内容が変更されると自動的に更新）

### ⚠️ 一部の自動修正が行われる

以下の修正が自動的に行われます：

1. **CSS読み込みの修正**
   - `rel="preload"` → `rel="stylesheet"`に変換
   - `onload`属性を削除

2. **文字エンコーディングの明示**
   - `text/html;charset=utf-8`としてBlobを作成

### 📝 プレビューに表示される内容

プレビューには、HTMLソースに含まれる以下の内容が表示されます：

- **HTMLの構造**: すべてのHTMLタグ、要素、属性
- **CSSスタイル**: 
  - `<style>`タグ内のCSS
  - 外部CSSファイル（`<link rel="stylesheet">`）
  - インラインスタイル（`style`属性）
- **JavaScript**: `<script>`タグ内のJavaScriptコード（実行される）
- **画像**: `<img>`タグで指定された画像
- **リンク**: `<a>`タグで指定されたリンク
- **フォーム**: `<form>`要素とその入力フィールド
- **その他のHTML要素**: すべての標準HTML要素

## 確認方法

### 1. エディタとプレビューの対応関係

エディタに以下のHTMLを入力すると：
```html
<!DOCTYPE html>
<html>
<head>
    <title>テスト</title>
    <style>
        h1 { color: red; }
    </style>
</head>
<body>
    <h1>こんにちは</h1>
    <p>これはテストです。</p>
</body>
</html>
```

プレビューには：
- 赤い「こんにちは」という見出し
- 「これはテストです。」という段落

が表示されます。

### 2. リアルタイム更新の確認

1. エディタでHTMLを編集
2. プレビューが自動的に更新されることを確認
3. 変更が即座に反映されることを確認

### 3. ダウンロード機能で確認

「⬇️ HTMLとして保存」ボタンをクリックして、ダウンロードしたHTMLファイルを確認すると、エディタに入力されたHTMLソースと同じ内容が保存されます。

## 制限事項

### 相対パスの問題

相対パスで指定されたリソース（CSS、JS、画像など）は、Blob URLのコンテキストでは解決されない場合があります。

**例：**
```html
<link rel="stylesheet" href="../common/css/style.css">
<img src="images/photo.jpg">
```

これらの相対パスは、プレビューでは読み込まれない可能性があります。

**解決方法：**
- 絶対URLを使用する（`https://example.com/css/style.css`）
- CDNから読み込む
- インラインで記述する（`<style>`タグ内にCSSを記述）

### 外部リソースの読み込み

外部のCSSファイルやJavaScriptファイルは、CORS（Cross-Origin Resource Sharing）の設定によっては読み込まれない場合があります。

## まとめ

- ✅ **プレビューはHTMLソースから生成される**
- ✅ **リアルタイムで更新される**
- ✅ **一部の自動修正が行われる（CSS読み込みの修正）**
- ⚠️ **相対パスのリソースは読み込まれない場合がある**

プレビューに表示されている内容は、エディタに入力されたHTMLソースがブラウザによってレンダリングされた結果です。

