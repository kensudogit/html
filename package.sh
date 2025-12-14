#!/bin/bash
# HTMLエディタ パッケージ作成スクリプト（macOS/Linux用）

echo "========================================"
echo "HTMLエディタ パッケージ作成"
echo "========================================"
echo ""

# パッケージディレクトリ名
PACKAGE_NAME="html_editor_package"
PACKAGE_DIR="../${PACKAGE_NAME}"

echo "パッケージディレクトリを作成中..."
if [ -d "$PACKAGE_DIR" ]; then
    echo "既存のパッケージディレクトリを削除中..."
    rm -rf "$PACKAGE_DIR"
fi
mkdir -p "$PACKAGE_DIR"

echo ""
echo "必要なファイルをコピー中..."

# メインファイル
cp web_html_editor.py "$PACKAGE_DIR/"
cp html_editor.py "$PACKAGE_DIR/"
cp requirements.txt "$PACKAGE_DIR/"
cp SETUP.md "$PACKAGE_DIR/"
if [ -f README.md ]; then
    cp README.md "$PACKAGE_DIR/"
fi

echo ""
echo "========================================"
echo "パッケージ作成完了！"
echo "========================================"
echo ""
echo "パッケージの場所: $PACKAGE_DIR"
echo ""
echo "次の手順:"
echo "1. $PACKAGE_DIR フォルダを他のPCにコピー"
echo "2. SETUP.md の手順に従ってセットアップ"
echo ""

