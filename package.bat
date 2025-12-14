@echo off
REM HTMLエディタ パッケージ作成スクリプト（Windows用）

echo ========================================
echo HTMLエディタ パッケージ作成
echo ========================================
echo.

REM パッケージディレクトリ名
set PACKAGE_NAME=html_editor_package
set PACKAGE_DIR=..\%PACKAGE_NAME%

echo パッケージディレクトリを作成中...
if exist "%PACKAGE_DIR%" (
    echo 既存のパッケージディレクトリを削除中...
    rmdir /s /q "%PACKAGE_DIR%"
)
mkdir "%PACKAGE_DIR%"

echo.
echo 必要なファイルをコピー中...

REM メインファイル
copy web_html_editor.py "%PACKAGE_DIR%\" >nul
copy html_editor.py "%PACKAGE_DIR%\" >nul
copy requirements.txt "%PACKAGE_DIR%\" >nul
copy SETUP.md "%PACKAGE_DIR%\" >nul
if exist README.md copy README.md "%PACKAGE_DIR%\" >nul

echo.
echo ========================================
echo パッケージ作成完了！
echo ========================================
echo.
echo パッケージの場所: %PACKAGE_DIR%
echo.
echo 次の手順:
echo 1. %PACKAGE_DIR% フォルダを他のPCにコピー
echo 2. SETUP.md の手順に従ってセットアップ
echo.
pause

