# プレビュー表示の形式について

## 概要

HTMLエディタのプレビュー機能は、エディタに入力されたHTMLソースコードを実際のWebページとして表示する機能です。

## 表示形式の詳細

### 1. 技術的な実装

プレビューは以下の技術を使用して実装されています：

#### HTML要素
```html
<iframe id="preview" class="preview" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe>
```

- **iframe要素**: 独立したHTMLドキュメントを表示するための要素
- **sandbox属性**: セキュリティのために制限を設定
  - `allow-same-origin`: 同じオリジンからのアクセスを許可
  - `allow-scripts`: JavaScriptの実行を許可
  - `allow-forms`: フォームの送信を許可
  - `allow-popups`: ポップアップウィンドウを許可

#### JavaScript実装
```javascript
function updatePreview() {
    const editor = getEditor();
    const preview = document.getElementById('preview');
    if (!editor || !preview) return;
    
    const content = editor.value;  // エディタのHTMLソースを取得
    const blob = new Blob([content], { type: 'text/html' });  // Blobオブジェクトを作成
    const url = URL.createObjectURL(blob);  // Blob URLを生成
    preview.src = url;  // iframeのsrcに設定
}
```

### 2. 表示の流れ

1. **HTMLソースの取得**
   - エディタ（textarea）に入力されたHTMLソースコードを取得

2. **Blobオブジェクトの作成**
   - HTMLソースを`Blob`オブジェクトとして作成
   - MIMEタイプ: `text/html`

3. **Blob URLの生成**
   - `URL.createObjectURL()`を使用してBlob URLを生成
   - 例: `blob:http://localhost:5000/abc123-def456-...`

4. **iframeへの設定**
   - 生成されたBlob URLをiframeの`src`属性に設定
   - iframe内でHTMLが実際のWebページとしてレンダリングされる

### 3. 表示される内容

プレビューには以下の内容が表示されます：

- **HTMLの構造**: HTMLタグ、要素、属性など
- **CSSスタイル**: `<style>`タグやインラインスタイル
- **JavaScript**: `<script>`タグ内のJavaScriptコード（実行される）
- **画像**: `<img>`タグで指定された画像（相対パスは動作しない場合がある）
- **リンク**: `<a>`タグで指定されたリンク
- **フォーム**: `<form>`要素とその入力フィールド
- **その他のHTML要素**: すべての標準HTML要素

### 4. リアルタイム更新

プレビューは以下のタイミングで自動的に更新されます：

- エディタの内容が変更されたとき（入力、削除、貼り付けなど）
- ファイルを読み込んだとき
- ファイルを保存したとき
- ファイルを再読み込みしたとき

### 5. 制限事項

#### 相対パス
- 画像やCSSファイルなどの相対パスは、Blob URLのコンテキストでは解決されない場合があります
- 例: `<img src="images/photo.jpg">` は表示されない可能性があります

#### 外部リソース
- 外部のCSSファイルやJavaScriptファイルは読み込まれます
- CDNから読み込むリソースは正常に動作します

#### セキュリティ
- `sandbox`属性により、一部の機能が制限される場合があります
- クロスオリジンリクエストは制限される可能性があります

### 6. CSSスタイル

プレビューエリアのスタイル：

```css
.preview {
    width: 100%;
    height: 600px;
    border: none;
    background: white;
}
```

- **幅**: 100%（親要素の幅に合わせる）
- **高さ**: 600px（固定）
- **背景**: 白色
- **ボーダー**: なし

### 7. プレビューと実際のWebページの違い

| 項目 | プレビュー | 実際のWebページ |
|------|-----------|----------------|
| URL | `blob:http://...` | `http://example.com/page.html` |
| 相対パス | 解決されない場合がある | 正常に解決される |
| セキュリティ | sandbox制限あり | 通常の制限 |
| 更新 | リアルタイム | ページリロードが必要 |

## 使用例

### 基本的なHTML
```html
<!DOCTYPE html>
<html>
<head>
    <title>テストページ</title>
</head>
<body>
    <h1>こんにちは</h1>
    <p>これはプレビューです。</p>
</body>
</html>
```

このHTMLをエディタに入力すると、プレビューには「こんにちは」という見出しと「これはプレビューです。」という段落が表示されます。

### CSSを含むHTML
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        h1 { color: blue; }
        p { font-size: 18px; }
    </style>
</head>
<body>
    <h1>スタイル付き見出し</h1>
    <p>スタイル付き段落</p>
</body>
</html>
```

プレビューには、青い見出しと18pxの段落が表示されます。

### JavaScriptを含むHTML
```html
<!DOCTYPE html>
<html>
<head>
    <title>JavaScriptテスト</title>
</head>
<body>
    <button onclick="alert('こんにちは！')">クリック</button>
    <script>
        console.log('ページが読み込まれました');
    </script>
</body>
</html>
```

プレビューにはボタンが表示され、クリックするとアラートが表示されます。

## まとめ

プレビュー表示は、HTMLソースコードをBlob URLとしてiframeに読み込むことで、実際のWebページとして表示する仕組みです。これにより、エディタで編集したHTMLがどのように表示されるかをリアルタイムで確認できます。

