#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebベースHTMLエディタ
ブラウザ上でHTMLファイルを編集できるWebアプリケーション
"""

# このファイルは、FlaskでHTML編集UIを提供するメインアプリです。
# 主要機能: アップロード/保存/検索/構文チェック/プレビュー表示（iframe+Blob URL）

import os
import sys
import argparse
import shutil
import tempfile
import traceback
import base64
import json
import zipfile
import sqlite3
import yaml
import io
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for, send_file, session
from html_editor import HTMLEditor
from bs4 import BeautifulSoup
import secrets

app = Flask(__name__)

# リクエストログ（Railway環境でのデバッグ用）
@app.before_request
def log_request_info():
    """すべてのリクエストをログに記録"""
    try:
        msg = f"=== リクエスト受信 ===\nMethod: {request.method}\nPath: {request.path}\nURL: {request.url}\nRemote Address: {request.remote_addr}\nUser Agent: {request.headers.get('User-Agent', 'N/A')}"
        app.logger.info(msg)
        print(msg, flush=True)  # printも追加して確実にログを出力
    except Exception as e:
        app.logger.error(f"リクエストログ記録エラー: {e}")
        print(f"リクエストログ記録エラー: {e}", flush=True)

# CORS設定（Railway環境でのAPIリクエストを許可）
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    app.logger.info(f"=== レスポンス送信 ===")
    app.logger.info(f"Status: {response.status_code}")
    app.logger.info(f"Path: {request.path}")
    return response

# セッション管理の設定
# SECRET_KEYはセッションの暗号化に使用される
# 環境変数で指定されていない場合は、ランダムな32バイトの16進数文字列を生成
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Vercel環境では/tmpディレクトリを使用
if os.environ.get('VERCEL'):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'

# デフォルトHTMLディレクトリ（アップロードフォルダを使用）
app.config['DEFAULT_HTML_DIRECTORY'] = None

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB制限

# セッション別のファイル管理用ディクショナリ
# キー: セッションID（文字列）
# 値: ファイル情報の辞書 {'html_editor': HTMLEditorオブジェクト, 'html_file_path': ファイルパス}
# これにより、複数のユーザー（セッション）が同時に異なるHTMLファイルを編集できる
session_files = {}

# アップロードフォルダを作成
UPLOAD_DIR = Path(app.config['UPLOAD_FOLDER'])
try:
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
except Exception as e:
    # Vercel環境などでディレクトリ作成に失敗した場合は警告のみ
    if os.environ.get('VERCEL'):
        pass  # Vercel環境では/tmpは既に存在する
    else:
        print(f"Warning: Could not create upload directory: {e}", file=sys.stderr)

# フロントエンドのビルドディレクトリ
BASE_DIR = Path(__file__).parent
# Railway環境でのパス解決を改善（複数のパスを試す）
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'
# 代替パス（Railway環境でのパス解決の問題に対応）
_ALTERNATIVE_PATHS = [
    BASE_DIR / 'frontend' / 'dist',
    Path('frontend') / 'dist',
    Path('/app') / 'frontend' / 'dist',
    Path('/app') / 'dist',
    Path(os.getcwd()) / 'frontend' / 'dist',
    Path(os.getcwd()) / 'dist',
    Path('/usr/src/app') / 'frontend' / 'dist',
    Path('/usr/src/app') / 'dist',
]

# 大学データ管理用のデータベースパス
DB_PATH = UPLOAD_DIR / 'university_data.db'
UNIVERSITY_CONFIG_DIR = UPLOAD_DIR / 'university_configs'
UNIVERSITY_CONFIG_DIR.mkdir(exist_ok=True, parents=True)

# データベースの初期化
def init_database():
    """大学データ管理用のデータベースを初期化"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 大学マスタテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ページタイトルマスタテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_titles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 大学ごとのページデータテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS university_page_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            page_title_id INTEGER NOT NULL,
            content TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (page_title_id) REFERENCES page_titles(id),
            UNIQUE(university_id, page_title_id)
        )
    ''')
    
    # デフォルトのページタイトルを挿入
    default_titles = [
        '入学手続TOP',
        '個人情報取り扱いに関する同意条項宣誓書',
        '本人情報',
        '健康状況',
        '保護者情報',
        '身元保証人情報',
        '緊急連絡先情報',
        '入学前セミナー受講調査',
        '写真アップロード',
        '書類アップロード',
        'アンケート',
        '学費負担者情報',
        '外国語の履修に関する調査',
        '父母等の連絡',
        '誓約書',
        'アドミッション・ポリシー',
        '家族情報',
        '通学住所情報',
        '利用規約・個人情報取扱いに関する同意条項',
        '言語選択申請'
    ]
    
    for i, title in enumerate(default_titles):
        cursor.execute('''
            INSERT OR IGNORE INTO page_titles (title, display_order) 
            VALUES (?, ?)
        ''', (title, i))
    
    conn.commit()
    conn.close()

# アプリケーション起動時にデータベースを初期化
init_database()

# HTMLエディタのテンプレート
EDITOR_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTMLエディタ{% if filename %} - {{ filename }}{% endif %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* 洗練されたデザインシステム */
        :root {
            --primary-color: #6366f1;
            --primary-dark: #4f46e5;
            --primary-light: #818cf8;
            --secondary-color: #8b5cf6;
            --success-color: #10b981;
            --success-dark: #059669;
            --info-color: #3b82f6;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --bg-tertiary: #f1f5f9;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-tertiary: #64748b;
            --border-color: #e2e8f0;
            --border-light: #f1f5f9;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --shadow-2xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            background-attachment: fixed;
            color: var(--text-primary);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            padding: 12px 24px;
            box-shadow: var(--shadow-lg);
            position: relative;
            overflow: hidden;
        }
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 100%);
            pointer-events: none;
        }
        .header > div {
            position: relative;
            z-index: 1;
        }
        .header h1 {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 2px;
            letter-spacing: -0.3px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .header p {
            opacity: 0.95;
            font-size: 12px;
            font-weight: 400;
            letter-spacing: 0.1px;
        }
        .header > div > div:last-child {
            display: flex !important;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }
        .header .btn {
            white-space: nowrap;
            display: inline-block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 32px;
        }
        .toolbar {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: flex !important;
            gap: 4px;
            flex-wrap: wrap;
            align-items: center;
            overflow-x: auto;
            overflow-y: visible;
            min-height: 60px;
            width: 100%;
        }
        .toolbar button {
            display: inline-block !important;
            visibility: visible !important;
            position: relative !important;
            z-index: 100 !important;
            flex-shrink: 0;
            white-space: nowrap;
        }
        #uploadBtnMain {
            background: #667eea !important;
            border-color: #5568d3 !important;
            font-weight: 600;
            box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
            display: inline-block !important;
            visibility: visible !important;
            opacity: 1 !important;
            position: relative !important;
            z-index: 100 !important;
            flex-shrink: 0 !important;
        }
        #uploadBtnMain:hover {
            background: #5568d3 !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.4);
        }
        #downloadBtn {
            display: inline-block !important;
            visibility: visible !important;
            position: relative !important;
            z-index: 100 !important;
            flex-shrink: 0 !important;
        }
        #downloadBtn:not(:disabled) {
            opacity: 1 !important;
        }
        #downloadBtn:disabled {
            opacity: 0.5 !important;
            cursor: not-allowed;
        }
        .toolbar::-webkit-scrollbar {
            height: 6px;
        }
        .toolbar::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }
        .toolbar::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 3px;
        }
        .toolbar::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: var(--radius-md);
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all var(--transition-base);
            position: relative;
            overflow: hidden;
            letter-spacing: 0.3px;
            box-shadow: var(--shadow-sm);
        }
        .btn::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        .btn:hover::before {
            width: 300px;
            height: 300px;
        }
        .btn:active {
            transform: scale(0.98);
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            color: white;
            box-shadow: var(--shadow-md);
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary-color) 100%);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .btn-success {
            background: linear-gradient(135deg, var(--success-color) 0%, var(--success-dark) 100%);
            color: white;
            box-shadow: var(--shadow-md);
        }
        .btn-success:hover {
            background: linear-gradient(135deg, var(--success-dark) 0%, var(--success-color) 100%);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .btn-info {
            background: linear-gradient(135deg, var(--info-color) 0%, #2563eb 100%);
            color: white;
            box-shadow: var(--shadow-md);
        }
        .btn-info:hover {
            background: linear-gradient(135deg, #2563eb 0%, var(--info-color) 100%);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .btn-danger {
            background: linear-gradient(135deg, var(--danger-color) 0%, #dc2626 100%);
            color: white;
            box-shadow: var(--shadow-md);
        }
        .btn-danger:hover {
            background: linear-gradient(135deg, #dc2626 0%, var(--danger-color) 100%);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .btn-warning {
            background: linear-gradient(135deg, var(--warning-color) 0%, #d97706 100%);
            color: white;
            box-shadow: var(--shadow-md);
        }
        .btn-warning:hover {
            background: linear-gradient(135deg, #d97706 0%, var(--warning-color) 100%);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .editor-container {
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            position: relative;
            height: 600px;
            min-height: 400px;
        }
        .editor-container.free-mode {
            height: calc(100vh - 200px);
            min-height: 500px;
        }
        @media (max-width: 1024px) {
            .editor-container {
                flex-direction: column;
                height: auto;
            }
            .resizer {
                display: none;
            }
        }
        .resizer {
            width: 6px;
            background: var(--border-color);
            cursor: col-resize;
            position: relative;
            flex-shrink: 0;
            z-index: 10;
            transition: all var(--transition-base);
        }
        .editor-container.free-mode .resizer {
            display: none;
        }
        /* 通常モードでのパネルリサイズハンドル */
        .editor-panel .panel-resize-handle {
            position: absolute;
            background: transparent;
            z-index: 1000;
            transition: background 0.2s;
        }
        .editor-panel .panel-resize-handle:hover {
            background: rgba(99, 102, 241, 0.2);
        }
        .editor-panel .panel-resize-handle.n {
            top: 0;
            left: 8px;
            right: 8px;
            height: 8px;
            cursor: n-resize;
        }
        .editor-panel .panel-resize-handle.s {
            bottom: 0;
            left: 8px;
            right: 8px;
            height: 8px;
            cursor: s-resize;
        }
        .editor-panel .panel-resize-handle.e {
            top: 8px;
            right: 0;
            bottom: 8px;
            width: 8px;
            cursor: e-resize;
        }
        .editor-panel .panel-resize-handle.w {
            top: 8px;
            left: 0;
            bottom: 8px;
            width: 8px;
            cursor: w-resize;
        }
        .editor-panel .panel-resize-handle.ne {
            top: 0;
            right: 0;
            width: 12px;
            height: 12px;
            cursor: ne-resize;
        }
        .editor-panel .panel-resize-handle.nw {
            top: 0;
            left: 0;
            width: 12px;
            height: 12px;
            cursor: nw-resize;
        }
        .editor-panel .panel-resize-handle.se {
            bottom: 0;
            right: 0;
            width: 12px;
            height: 12px;
            cursor: se-resize;
        }
        .editor-panel .panel-resize-handle.sw {
            bottom: 0;
            left: 0;
            width: 12px;
            height: 12px;
            cursor: sw-resize;
        }
        .editor-panel .panel-resize-handle.resizing {
            background: rgba(99, 102, 241, 0.4);
        }
        /* 自由配置モードでは通常のリサイズハンドルを使用 */
        .editor-container.free-mode .editor-panel .panel-resize-handle {
            display: none;
        }
        .resizer:hover {
            background: var(--primary-light);
            width: 8px;
        }
        .resizer::before {
            content: '';
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 4px;
            height: 40px;
            background: var(--primary-color);
            border-radius: 2px;
            opacity: 0;
            transition: opacity var(--transition-base);
        }
        .resizer:hover::before {
            opacity: 0.6;
        }
        .resizer.resizing {
            background: var(--primary-color);
            width: 8px;
        }
        .resizer.resizing::before {
            opacity: 1;
        }
        .editor-panel {
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            overflow: hidden;
            position: relative;
            flex: 1;
            min-width: 200px;
            min-height: 300px;
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border-light);
            transition: all var(--transition-base);
        }
        .editor-container.free-mode .editor-panel {
            position: absolute;
            flex: none;
            z-index: 100;
        }
        .editor-panel.dragging {
            z-index: 1000;
            box-shadow: var(--shadow-2xl);
            opacity: 0.95;
        }
        .editor-panel.resizing {
            z-index: 1000;
        }
        .editor-panel:hover {
            box-shadow: var(--shadow-2xl);
        }
        .editor-panel:first-child {
            border-top-right-radius: 0;
            border-bottom-right-radius: 0;
        }
        .editor-panel:last-child {
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }
        .editor-container.free-mode .editor-panel:first-child,
        .editor-container.free-mode .editor-panel:last-child {
            border-radius: var(--radius-lg);
        }
        /* ドラッグ可能なヘッダー */
        .panel-header {
            cursor: move;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header.dragging {
            cursor: grabbing;
        }
        .btn-fullscreen {
            transition: all 0.2s;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .btn-fullscreen:hover {
            background: rgba(255,255,255,0.3) !important;
            transform: scale(1.1);
        }
        /* 全画面表示スタイル */
        .panel-fullscreen {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 10000 !important;
            margin: 0 !important;
            border-radius: 0 !important;
        }
        .panel-fullscreen .panel-header {
            border-radius: 0 !important;
        }
        .panel-fullscreen .editor-wrapper,
        .panel-fullscreen .editor,
        .panel-fullscreen .preview {
            height: calc(100vh - 60px) !important;
        }
        /* リサイズハンドル */
        .resize-handle {
            position: absolute;
            background: transparent;
            z-index: 1000;
        }
        .resize-handle.n {
            top: 0;
            left: 8px;
            right: 8px;
            height: 8px;
            cursor: n-resize;
        }
        .resize-handle.s {
            bottom: 0;
            left: 8px;
            right: 8px;
            height: 8px;
            cursor: s-resize;
        }
        .resize-handle.e {
            top: 8px;
            right: 0;
            bottom: 8px;
            width: 8px;
            cursor: e-resize;
        }
        .resize-handle.w {
            top: 8px;
            left: 0;
            bottom: 8px;
            width: 8px;
            cursor: w-resize;
        }
        .resize-handle.ne {
            top: 0;
            right: 0;
            width: 12px;
            height: 12px;
            cursor: ne-resize;
        }
        .resize-handle.nw {
            top: 0;
            left: 0;
            width: 12px;
            height: 12px;
            cursor: nw-resize;
        }
        .resize-handle.se {
            bottom: 0;
            right: 0;
            width: 12px;
            height: 12px;
            cursor: se-resize;
        }
        .resize-handle.sw {
            bottom: 0;
            left: 0;
            width: 12px;
            height: 12px;
            cursor: sw-resize;
        }
        .resize-handle:hover {
            background: rgba(99, 102, 241, 0.2);
        }
        .resize-handle.resizing {
            background: rgba(99, 102, 241, 0.4);
        }
        .panel-header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            padding: 18px 24px;
            border-bottom: none;
            font-weight: 600;
            color: white;
            font-size: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: var(--shadow-md);
            position: relative;
        }
        .panel-header::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
        }
        .panel-header span {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.3px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        #previewPanel .panel-header {
            background: linear-gradient(135deg, var(--success-color) 0%, var(--success-dark) 100%);
        }
        #previewPanel .panel-header span {
            font-size: 17px;
        }
        .editor-wrapper {
            position: relative;
            width: 100%;
            height: 600px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .editor-container.free-mode .editor-wrapper {
            height: calc(100% - 60px);
        }
        .editor {
            width: 100%;
            height: 600px;
            border: none;
            padding: 20px;
            font-family: 'Fira Code', 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.7;
            resize: vertical;
            background: #1a1a1a;
            color: #e4e4e4;
            position: relative;
            z-index: 1;
            transition: all var(--transition-base);
            flex: 1;
        }
        .editor-container.free-mode .editor {
            height: 100%;
            resize: none;
        }
        .editor:focus {
            outline: none;
            background: #1e1e1e;
        }
        .editor-highlight {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 2;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            padding: 15px;
            box-sizing: border-box;
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow: auto;
            color: transparent;
            /* textareaと同じスタイルを維持 */
            border: none;
            resize: none;
            /* スクロールバーを非表示（textareaのスクロールバーと重ならないように） */
            scrollbar-width: none; /* Firefox */
            -ms-overflow-style: none; /* IE/Edge */
        }
        .editor-highlight::-webkit-scrollbar {
            display: none; /* Chrome/Safari */
        }
        .highlight-mark {
            background-color: rgba(255, 255, 0, 0.4);
            border-radius: 2px;
            position: absolute;
            pointer-events: none;
            animation: highlightBlink 1.5s ease-in-out infinite;
        }
        @keyframes highlightBlink {
            0%, 100% {
                background-color: rgba(255, 255, 0, 0.4);
                opacity: 1;
            }
            50% {
                background-color: rgba(255, 255, 0, 0.8);
                opacity: 0.8;
            }
        }
        .preview {
            width: 100%;
            height: 600px;
            border: none;
            border-top: none;
            background: #ffffff;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.02);
            transition: all var(--transition-base);
            position: relative;
            flex: 1;
        }
        .editor-container.free-mode .preview {
            height: calc(100% - 60px);
        }
        .preview:hover {
            box-shadow: inset 0 0 40px rgba(0,0,0,0.03);
        }
        /* プレビューエリアのコンテナ */
        #previewPanel {
            position: relative;
            overflow: hidden;
        }
        #previewPanel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #48bb78 0%, #38a169 100%);
            z-index: 1;
        }
        #previewPanel::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            background: linear-gradient(to bottom, rgba(72, 187, 120, 0.03) 0%, transparent 20px);
            z-index: 0;
        }
        /* プレビュー内のコンテンツを読みやすく */
        #preview {
            background: #ffffff;
        }
        /* プレビューが読み込み中の場合の表示 */
        #preview:not([src]) {
            background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #preview:not([src])::before {
            content: '👁️ プレビューがここに表示されます';
            color: #718096;
            font-size: 18px;
            font-weight: 500;
            opacity: 0.7;
        }
        /* プレビュー内の要素ハイライト */
        .preview-highlight {
            outline: 3px solid #667eea !important;
            outline-offset: 2px !important;
            background-color: rgba(102, 126, 234, 0.1) !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.3) !important;
            border-radius: 2px !important;
        }
        .preview-highlight-label {
            outline: 3px solid #48bb78 !important;
            outline-offset: 2px !important;
            background-color: rgba(72, 187, 120, 0.15) !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 0 0 2px rgba(72, 187, 120, 0.4) !important;
            border-radius: 2px !important;
        }
        .info-panel {
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            padding: 24px;
            box-shadow: var(--shadow-xl);
            border: 1px solid var(--border-light);
            transition: all var(--transition-base);
        }
        .info-panel:hover {
            box-shadow: var(--shadow-2xl);
        }
        .info-item {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e2e8f0;
        }
        .info-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        .info-label {
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 8px;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .info-value {
            color: var(--text-primary);
            font-size: 15px;
            font-weight: 500;
        }
        .status {
            padding: 10px 15px;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        .status {
            animation: slideDown var(--transition-base);
        }
        /* 画面比較用スタイル */
        .comparison-screen {
            background: white;
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            border: 2px solid var(--border-color);
            overflow: hidden;
            position: relative;
            transition: all var(--transition-base);
            display: flex;
            flex-direction: column;
        }
        .comparison-screen:hover {
            box-shadow: var(--shadow-2xl);
            border-color: var(--primary-color);
        }
        .comparison-screen.selected {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }
        .comparison-screen-header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            padding: 12px 16px;
            color: white;
            font-weight: 600;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: move;
            user-select: none;
        }
        .comparison-screen-header .screen-actions {
            display: flex;
            gap: 8px;
        }
        .comparison-screen-header .screen-actions button {
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            transition: all var(--transition-base);
        }
        .comparison-screen-header .screen-actions button:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .comparison-screen-preview {
            flex: 1;
            overflow: auto;
            background: #f8fafc;
            position: relative;
        }
        .comparison-screen-preview iframe {
            width: 100%;
            height: 100%;
            border: none;
            background: white;
        }
        .comparison-screen-preview pre {
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: #e4e4e4;
            font-family: 'Fira Code', 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.6;
            height: 100%;
            overflow: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            border-radius: 0;
        }
        .comparison-screen-preview pre::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        .comparison-screen-preview pre::-webkit-scrollbar-track {
            background: #2a2a2a;
        }
        .comparison-screen-preview pre::-webkit-scrollbar-thumb {
            background: #555;
            border-radius: 4px;
        }
        .comparison-screen-preview pre::-webkit-scrollbar-thumb:hover {
            background: #666;
        }
        .comparison-screen-info {
            padding: 10px 16px;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            font-size: 11px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .comparison-screen-info .diff-badge {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 600;
        }
        .comparison-screen-info .diff-badge.same {
            background: rgba(16, 185, 129, 0.1);
            color: #059669;
        }
        .comparison-screen-info .diff-badge.different {
            background: rgba(239, 68, 68, 0.1);
            color: #dc2626;
        }
        .comparison-grid {
            display: grid;
            gap: 15px;
        }
        .comparison-grid.grid-layout {
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
        }
        .comparison-grid.horizontal-layout {
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        }
        .comparison-grid.vertical-layout {
            grid-template-columns: 1fr;
        }
        .comparison-mode-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(99, 102, 241, 0.05);
            border: 2px dashed var(--primary-color);
            pointer-events: none;
            z-index: 100;
            display: none;
        }
        .comparison-mode .comparison-mode-overlay {
            display: block;
        }
        .comparison-diff-highlight {
            outline: 3px solid #ef4444 !important;
            outline-offset: 2px !important;
            background-color: rgba(239, 68, 68, 0.1) !important;
        }
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .status.success {
            background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
            color: #065f46;
            border: 2px solid var(--success-color);
            box-shadow: var(--shadow-md);
        }
        .status.error {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            color: #991b1b;
            border: 2px solid var(--danger-color);
            box-shadow: var(--shadow-md);
        }
        .search-box {
            flex: 1;
            min-width: 200px;
            padding: 10px 14px;
            border: 2px solid var(--border-color);
            border-radius: var(--radius-md);
            font-size: 13px;
            transition: all var(--transition-base);
            background: var(--bg-primary);
            color: var(--text-primary);
        }
        .search-box:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        .search-box:hover {
            border-color: var(--primary-light);
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(4px);
            animation: fadeIn var(--transition-base);
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .modal-content {
            background: var(--bg-primary);
            margin: 5% auto;
            padding: 32px;
            border-radius: var(--radius-xl);
            width: 90%;
            max-width: 700px;
            box-shadow: var(--shadow-2xl);
            border: 1px solid var(--border-light);
            animation: slideUp var(--transition-slow);
            position: relative;
        }
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .close {
            color: var(--text-tertiary);
            float: right;
            font-size: 28px;
            font-weight: 300;
            cursor: pointer;
            line-height: 1;
            transition: all var(--transition-fast);
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius-sm);
        }
        .close:hover {
            color: var(--text-primary);
            background: var(--bg-tertiary);
            transform: rotate(90deg);
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #4a5568;
        }
        .form-input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid var(--border-color);
            border-radius: var(--radius-md);
            font-size: 14px;
            transition: all var(--transition-base);
            background: var(--bg-primary);
            color: var(--text-primary);
        }
        .form-input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        .form-input:hover {
            border-color: var(--primary-light);
        }
        .btn-warning {
            background: #f59e0b;
            color: white;
        }
        .btn-warning:hover {
            background: #d97706;
        }
        .error-item {
            padding: 14px 16px;
            margin-bottom: 10px;
            border-radius: var(--radius-md);
            border-left: 4px solid;
            box-shadow: var(--shadow-sm);
            transition: all var(--transition-base);
        }
        .error-item:hover {
            transform: translateX(4px);
            box-shadow: var(--shadow-md);
        }
        .error-item.error {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border-color: var(--danger-color);
        }
        .error-item.warning {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-color: var(--warning-color);
        }
        .error-item-header {
            font-weight: 600;
            margin-bottom: 5px;
        }
        .error-item-message {
            font-size: 14px;
            color: #4a5568;
        }
        .error-item-location {
            font-size: 12px;
            color: #718096;
            margin-top: 5px;
        }
        .error-item-link {
            color: #4299e1;
            cursor: pointer;
            text-decoration: underline;
        }
        .error-item-link:hover {
            color: #3182ce;
        }
        /* リモコン盤スタイル */
        #remoteControl {
            position: fixed;
            z-index: 10000;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-2xl);
            min-width: 200px;
            max-width: 280px;
            max-height: 90vh;
            height: auto;
            transition: all var(--transition-slow);
            user-select: none;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
        }
        #remoteControl.collapsed {
            min-width: auto;
            width: auto;
        }
        #remoteControl.collapsed .remote-control-content {
            display: none;
        }
        #remoteControl.collapsed .remote-control-header {
            border-radius: 8px;
        }
        .remote-control-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 8px 12px;
            border-radius: 8px 8px 0 0;
            cursor: move;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: white;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .remote-control-header:hover {
            background: linear-gradient(135deg, #5568d3 0%, #6b3fa0 100%);
        }
        .remote-control-title {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            font-weight: 700;
        }
        .remote-control-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .remote-control-toggle:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.1);
        }
        .remote-control-content {
            background: var(--bg-primary);
            padding: 14px;
            border-radius: 0 0 var(--radius-lg) var(--radius-lg);
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-height: calc(90vh - 60px);
            overflow-y: auto;
            overflow-x: hidden;
            flex: 1;
        }
        .remote-control-section {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .remote-control-section-title {
            font-size: 11px;
            font-weight: 700;
            color: #2d3748;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 4px;
            padding-bottom: 4px;
            border-bottom: 1px solid #e2e8f0;
        }
        .remote-control-buttons {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .remote-control-buttons .btn {
            width: 100%;
            font-size: 12px;
            padding: 8px 12px;
            text-align: center;
            font-weight: 600;
            border: 2px solid transparent;
            transition: all 0.2s ease;
        }
        .remote-control-buttons .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .remote-control-search {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .remote-control-search input {
            flex: 1;
            padding: 8px 10px;
            border: 2px solid #e2e8f0;
            border-radius: 6px;
            font-size: 12px;
            transition: all 0.2s ease;
        }
        .remote-control-search input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .remote-control-search .btn {
            flex: 0 0 auto;
            min-width: auto;
            padding: 8px 14px;
            font-size: 12px;
            font-weight: 600;
        }
        .remote-control-nav-buttons {
            display: flex;
            gap: 6px;
        }
        .remote-control-nav-buttons .btn {
            flex: 1;
            min-width: auto;
            padding: 8px 12px;
            font-size: 12px;
            font-weight: 600;
            background: #3b82f6;
            border: 2px solid #2563eb;
            color: white;
        }
        .remote-control-nav-buttons .btn:hover {
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        #remoteControl.dragging {
            opacity: 0.8;
            cursor: move;
        }
        .remote-control-content::-webkit-scrollbar {
            width: 8px;
        }
        .remote-control-content::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        .remote-control-content::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        .remote-control-content::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        /* 利用手順パネルスタイル（リモコン盤と同じデザイン） */
        #usageGuide {
            position: fixed;
            z-index: 9999;
            background: linear-gradient(135deg, var(--success-color) 0%, var(--success-dark) 100%);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-2xl);
            min-width: 280px;
            max-width: 90vw;
            transition: all var(--transition-slow);
            user-select: none;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }
        #usageGuide.collapsed {
            min-width: auto;
            width: auto;
        }
        #usageGuide.collapsed .usage-guide-content {
            display: none;
        }
        #usageGuide.collapsed .usage-guide-header {
            border-radius: var(--radius-lg);
        }
        .usage-guide-header {
            background: linear-gradient(135deg, var(--success-color) 0%, var(--success-dark) 100%);
            padding: 6px 10px;
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
            cursor: move;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: white;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .usage-guide-header:hover {
            background: linear-gradient(135deg, var(--success-dark) 0%, #047857 100%);
        }
        .usage-guide-title {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
        }
        .usage-guide-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .usage-guide-toggle:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.1);
        }
        .usage-guide-content {
            background: var(--bg-primary);
            padding: 12px;
            border-radius: 0 0 var(--radius-lg) var(--radius-lg);
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .usage-guide-step {
            padding: 10px;
            background: white;
            border-radius: var(--radius-md);
            border-left: 3px solid var(--success-color);
            box-shadow: var(--shadow-sm);
            margin-bottom: 8px;
        }
        .usage-guide-step-number {
            display: inline-block;
            width: 20px;
            height: 20px;
            background: var(--success-color);
            color: white;
            border-radius: 50%;
            text-align: center;
            line-height: 20px;
            font-size: 11px;
            font-weight: 700;
            margin-right: 8px;
        }
        .usage-guide-step-title {
            font-weight: 600;
            color: var(--text-primary);
            font-size: 12px;
            margin-bottom: 4px;
        }
        .usage-guide-step-content {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-top: 4px;
        }
        .usage-guide-step-content ul {
            margin: 4px 0;
            padding-left: 18px;
        }
        .usage-guide-step-content li {
            margin: 2px 0;
        }
        #usageGuide.dragging {
            opacity: 0.8;
            cursor: move;
        }
        .usage-guide-content::-webkit-scrollbar {
            width: 8px;
        }
        .usage-guide-content::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        .usage-guide-content::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        .usage-guide-content::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
    </style>
</head>
<body>
    <div class="header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1>📝 HTMLエディタ</h1>
                <p>ファイル: {{ filename if filename else 'ファイルを選択してください' }}</p>
            </div>
        </div>
    </div>
    
    <!-- 利用手順パネル -->
    <div id="usageGuide">
        <div class="usage-guide-header" id="usageGuideHeader">
            <div class="usage-guide-title">📖 利用手順</div>
            <button class="usage-guide-toggle" id="usageGuideToggle" title="開閉">▼</button>
        </div>
        <div class="usage-guide-content" id="usageGuideContent">
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">1</span>
                    ファイルのアップロード・編集
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>リモコン盤の「📤 アップロード」ボタンからHTMLファイルをアップロード</li>
                        <li>アップロード後、サーバーのアップロードフォルダにファイルが保存されます（元のファイルは変更されません）</li>
                        <li>左側のエディタでHTMLソースを編集可能</li>
                        <li>右側のプレビューでリアルタイムに変更内容を確認</li>
                        <li>「💾 保存」ボタンで編集内容を保存（Ctrl+Sでも保存可能）※アップロード先のファイルが更新されます</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">2</span>
                    自由配置モード（🪟 自由配置モード）
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>リモコン盤の「🪟 自由配置モード」ボタンをクリック</li>
                        <li>HTMLソースとプレビューウィンドウを自由に移動・リサイズ可能</li>
                        <li>ウィンドウのヘッダーをドラッグして移動</li>
                        <li>ウィンドウの端や角をドラッグしてリサイズ</li>
                        <li>配置は自動保存され、次回起動時にも復元されます</li>
                        <li>「📐 通常モード」で元の分割表示に戻せます</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">3</span>
                    画面比較機能（🖼️ 画面比較）
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>リモコン盤の「🖼️ 画面比較」ボタンをクリック</li>
                        <li>比較対象ディレクトリパスを入力（例: C:\universities）</li>
                        <li>「📁 ファイル読み込み」でHTML/CSSファイルを自動検出（最大27ファイル）</li>
                        <li>HTMLファイルとCSSファイルが自動的に関連付けられます</li>
                        <li>ファイル一覧から比較したいファイルを選択（チェックボックス）</li>
                        <li>レイアウト選択: グリッド表示 / 横並び / 縦並び</li>
                        <li>各画面のアクション:
                            <ul>
                                <li>✏️ 編集: 新しいタブでエディタを開く</li>
                                <li>⬇️ ダウンロード: ファイルをダウンロード</li>
                                <li>📊 分析: 画面の詳細分析</li>
                            </ul>
                        </li>
                        <li>「📊 比較レポート出力」でCSV形式の比較レポートをダウンロード</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">4</span>
                    HTML/CSS比較機能
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>画面比較モードで複数ファイルを選択すると自動的に比較が実行されます</li>
                        <li>HTML構造の比較: タグ、クラス、ID、属性の差分を検出</li>
                        <li>CSS比較: セレクタ、プロパティ、値の差分を検出</li>
                        <li>比較結果バッジに「HTML: X箇所, CSS: Y箇所」と表示</li>
                        <li>CSSファイルはシンタックスハイライト付きで表示</li>
                        <li>比較レポートにはHTML/CSSの両方の情報が含まれます</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">5</span>
                    差分検出とテンプレート生成（27大学のホームページ）
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>リモコン盤の「🔍 差分検出」ボタンをクリック</li>
                        <li>27校のHTMLファイルが保存されているディレクトリパスを入力</li>
                        <li>検出オプションを選択:
                            <ul>
                                <li>構造の差分: HTML構造の違いを検出</li>
                                <li>属性の差分: 属性値の違いを検出</li>
                                <li>詳細な差分情報を表示: より詳細な比較結果</li>
                            </ul>
                        </li>
                        <li>「🔍 差分検出実行」をクリックして処理開始</li>
                        <li>差分検出完了後、「🔀 最大公約数テンプレート生成」をクリック</li>
                        <li>共通部分と差分部分（変数化）を含むテンプレートが生成されます</li>
                        <li>「📥 差分レポートをダウンロード」で詳細な差分情報を取得</li>
                        <li>「📊 CSVでエクスポート」で比較結果をCSV形式で出力</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">6</span>
                    27大学のホームページ生成
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>テンプレート生成後、「🏫 27大学のホームページを生成」をクリック</li>
                        <li>各大学の現行デザインを保持したホームページが自動生成されます</li>
                        <li>生成されたファイルは「📦 ZIPファイルをダウンロード」で一括ダウンロード可能</li>
                        <li>各大学の個別ファイルも個別にダウンロードできます</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">7</span>
                    大学データ管理・YAML設定ファイルからページ一括生成（🏫 大学データ管理）
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li>リモコン盤の「🏫 大学データ管理」ボタンをクリック</li>
                        <li><strong>基本機能:</strong>
                            <ul style="margin-top: 8px; padding-left: 20px;">
                                <li>大学一覧から大学を選択、または新規大学を追加</li>
                                <li>ページタイトルを選択して、各大学のページデータを編集・保存</li>
                                <li>「⚙️ 表示位置設定」で各項目の表示位置・スタイルを設定</li>
                                <li>「🔀 ページ生成」で個別ページを生成</li>
                            </ul>
                        </li>
                        <li><strong>YAML設定ファイルから一括生成:</strong>
                            <ul style="margin-top: 8px; padding-left: 20px;">
                                <li>モーダル下部の「📄 YAML設定ファイルから一括生成」セクションを確認</li>
                                <li><strong>対象大学:</strong> 大学コードをカンマ区切りで入力（例: UNIV001,UNIV002）<br>
                                    空欄の場合は全大学が対象となります</li>
                                <li><strong>出力ディレクトリ:</strong> 生成ファイルの保存先を指定（空欄の場合はデフォルト）</li>
                                <li>「🚀 ページ一括生成」ボタンをクリック</li>
                                <li>university_pages_config.ymlの設定に基づいて、各大学の入学手続きWEBページ（全20ページ）が自動生成されます</li>
                                <li>生成されるページ: 入学手続TOP、個人情報同意、本人情報、健康状況、保護者情報、身元保証人情報、緊急連絡先情報、入学前セミナー受講調査、写真アップロード、書類アップロード、アンケート、学費負担者情報、外国語の履修に関する調査、父母等の連絡、誓約書、アドミッション・ポリシー、家族情報、通学住所情報、利用規約・個人情報取扱いに関する同意条項、言語選択申請</li>
                                <li>各ページには適切なフォームフィールド（テキスト、テキストエリア、日付、選択、チェックボックス、ラジオボタン、ファイルアップロードなど）が自動的に配置されます</li>
                                <li>生成完了後、生成結果が表示されます（対象大学数、生成ページ数、成功/失敗数など）</li>
                                <li>「📦 生成済みページをダウンロード」ボタンで、生成された全ページをZIPファイルとしてダウンロード可能</li>
                            </ul>
                        </li>
                        <li><strong>YAML設定ファイルのカスタマイズ:</strong>
                            <ul style="margin-top: 8px; padding-left: 20px;">
                                <li>university_pages_config.ymlファイルを編集することで、ページタイトル、フォームフィールド、大学ごとのカスタマイズ設定を変更できます</li>
                                <li>各大学のレイアウトテーマ、カラースキーム、表示順序などを個別に設定可能</li>
                            </ul>
                        </li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">8</span>
                    その他の主要機能
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li><strong>🔀 テンプレート統合:</strong> 複数ファイルから共通テンプレートを生成</li>
                        <li><strong>📤 デザイン出力:</strong> プレビューのDOMと主要CSSをJSON/CSVで出力</li>
                        <li><strong>🔍 検索・置換:</strong> HTMLソース内の文字列を検索・置換（Ctrl+F）</li>
                        <li><strong>⚠️ 構文チェック:</strong> HTMLの構文エラーを検出</li>
                        <li><strong>📁 ファイル一覧:</strong> 保存済みファイルの一覧を表示</li>
                        <li><strong>💾 保存:</strong> 編集内容を保存（Ctrl+S）</li>
                        <li><strong>⬇️ ダウンロード:</strong> 現在のHTMLファイルをダウンロード</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">8</span>
                    キーボードショートカット
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li><strong>Ctrl+S:</strong> ファイルを保存</li>
                        <li><strong>Ctrl+F:</strong> 検索・置換ダイアログを開く</li>
                        <li><strong>Ctrl+Z:</strong> 元に戻す（エディタ内）</li>
                        <li><strong>Ctrl+Y:</strong> やり直す（エディタ内）</li>
                        <li><strong>上下矢印キー:</strong> 検索結果間を移動（検索モード時）</li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">9</span>
                    ファイル形式と対応機能
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li><strong>HTMLファイル (.html, .htm):</strong>
                            <ul>
                                <li>リアルタイムプレビュー表示</li>
                                <li>構文チェック</li>
                                <li>DOM構造解析</li>
                                <li>CSS抽出・比較</li>
                            </ul>
                        </li>
                        <li><strong>CSSファイル (.css):</strong>
                            <ul>
                                <li>シンタックスハイライト表示</li>
                                <li>CSSルール解析</li>
                                <li>比較機能対応</li>
                            </ul>
                        </li>
                    </ul>
                </div>
            </div>
            
            <div class="usage-guide-step">
                <div class="usage-guide-step-title">
                    <span class="usage-guide-step-number">10</span>
                    トラブルシューティング
                </div>
                <div class="usage-guide-step-content">
                    <ul>
                        <li><strong>プレビューが表示されない:</strong> HTMLの構文エラーを確認（構文チェック機能を使用）</li>
                        <li><strong>ファイルが保存できない:</strong> ファイルパスの権限を確認</li>
                        <li><strong>比較機能が動作しない:</strong> ディレクトリパスが正しいか確認（絶対パス推奨）</li>
                        <li><strong>自由配置モードでウィンドウが見えない:</strong> ブラウザをリロードして初期位置に戻す</li>
                        <li><strong>CSS比較が正確でない:</strong> 外部CSSファイルも同じディレクトリに配置されているか確認</li>
                    </ul>
                </div>
            </div>
            
        </div>
    </div>
    
    <!-- リモコン盤 -->
    <div id="remoteControl">
        <div class="remote-control-header" id="remoteControlHeader">
            <div class="remote-control-title">🎮 リモコン盤</div>
            <button class="remote-control-toggle" id="remoteControlToggle" title="開閉">▼</button>
        </div>
        <div class="remote-control-content" id="remoteControlContent">
            <!-- ファイル操作セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">ファイル操作</div>
                <div class="remote-control-buttons">
                    <button class="btn btn-primary" id="uploadBtnMain" style="font-weight: 600; background: #667eea; border: 2px solid #5568d3; color: white;">
                        📤 アップロード
                    </button>
                    <button class="btn btn-success" onclick="downloadFile()" id="downloadBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #48bb78; border-color: #38a169; color: white;">
                        ⬇️ ダウンロード
                    </button>
                    <button class="btn btn-info" onclick="showFileList()" id="fileListBtn" style="font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;">📁 ファイル一覧</button>
                </div>
            </div>
            
            <!-- 編集操作セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">編集操作</div>
                <div class="remote-control-buttons">
                    <button class="btn btn-primary" onclick="saveFile()" id="saveBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #667eea; border: 2px solid #5568d3; color: white;">💾 保存</button>
                    <button class="btn btn-success" onclick="reloadFile()" id="reloadBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #48bb78; border: 2px solid #38a169; color: white;">🔄 再読み込み</button>
                    <button class="btn btn-danger" onclick="clearEditor()" id="clearBtn" style="font-weight: 600; background: #ef4444; border: 2px solid #dc2626; color: white;">🗑️ クリア</button>
                    <button class="btn btn-warning" onclick="showStructure()" id="structureBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #f59e0b; border: 2px solid #d97706; color: white;">📊 構造情報</button>
                    <button class="btn btn-danger" onclick="validateHTML()" id="validateBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #ef4444; border: 2px solid #dc2626; color: white;">⚠️ 構文チェック</button>
                    <button class="btn btn-info" onclick="showSearch()" id="searchBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;">🔍 検索・置換</button>
                    <button class="btn btn-warning" onclick="showDesignExport()" id="exportDesignBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #f59e0b; border: 2px solid #d97706; color: white;" title="プレビューのDOMと主要CSS(Computed Style)をJSON/CSVで出力して比較に使います">📤 デザイン出力</button>
                    <button class="btn btn-warning" onclick="toggleFreeMode()" id="freeModeBtn" style="font-weight: 600; background: #fbbf24; border: 2px solid #f59e0b; color: white;" title="ウィンドウを自由に移動・リサイズできるモードに切り替えます">🪟 自由配置モード</button>
                </div>
            </div>
            
            <!-- テンプレート統合セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">テンプレート統合</div>
                <div class="remote-control-buttons">
                    <button class="btn btn-warning" onclick="showTemplateMerge()" id="templateMergeBtn" style="font-weight: 600; background: #f59e0b; border: 2px solid #d97706; color: white;" title="複数のHTMLファイルを比較して共通テンプレートを生成">🔀 テンプレート統合</button>
                    <button class="btn btn-info" onclick="showDiffAnalysis()" id="diffAnalysisBtn" style="font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;" title="27校の大学ホームページの差分を検出">🔍 差分検出</button>
                    <button class="btn btn-primary" onclick="showScreenComparison()" id="screenComparisonBtn" style="font-weight: 600; background: #9333ea; border: 2px solid #7e22ce; color: white;" title="最大27大学の画面を並べて比較・編集">🖼️ 画面比較</button>
                    <button class="btn btn-success" onclick="showUniversityDataManagement()" id="universityDataBtn" style="font-weight: 600; background: #48bb78; border: 2px solid #38a169; color: white;" title="27大学の入学手続きページデータを管理">🏫 大学データ管理</button>
                </div>
            </div>
            
            <!-- 画面比較クイック操作セクション -->
            <div class="remote-control-section" id="screenComparisonQuickSection" style="display: none;">
                <div class="remote-control-section-title">画面比較クイック操作</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="quickComparisonDir" class="form-input" placeholder="C:\html" style="flex: 1; font-size: 11px; padding: 6px 10px;" title="比較対象ディレクトリパス">
                        <button class="btn btn-info" onclick="quickLoadComparisonFiles()" style="font-size: 11px; padding: 6px 12px; white-space: nowrap;" title="ファイルを読み込み">📁 読み込み</button>
                    </div>
                    <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                        <select id="quickLayout" class="form-input" style="flex: 1; min-width: 100px; font-size: 11px; padding: 6px 8px;" onchange="quickUpdateLayout()" title="レイアウト選択">
                            <option value="grid">グリッド</option>
                            <option value="horizontal">横並び</option>
                            <option value="vertical">縦並び</option>
                        </select>
                        <button class="btn btn-primary" onclick="quickToggleComparisonMode()" id="quickComparisonModeBtn" style="font-size: 11px; padding: 6px 12px; white-space: nowrap;" title="比較モード切り替え">比較モード</button>
                        <button class="btn btn-success" onclick="quickExportReport()" style="font-size: 11px; padding: 6px 12px; white-space: nowrap;" title="比較レポート出力">📊 レポート</button>
                    </div>
                    <div style="display: flex; gap: 5px; flex-wrap: wrap; font-size: 10px; color: #666;">
                        <span id="quickFileCount" style="padding: 4px 8px; background: #f0f4f8; border-radius: 4px;">ファイル: 0件</span>
                        <span id="quickSelectedCount" style="padding: 4px 8px; background: #e6ffed; border-radius: 4px;">選択: 0件</span>
                    </div>
                </div>
            </div>
            
            <!-- 要素検索セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">要素検索</div>
                <div class="remote-control-search">
                    <input type="text" id="searchBox" placeholder="ID、クラス、タグ、テキストで検索..." onkeypress="if(event.key==='Enter') searchElement()" {% if not filename %}disabled{% endif %}>
                    <button class="btn btn-info" onclick="searchElement()" id="searchElementBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;">検索</button>
                </div>
                <div class="remote-control-nav-buttons">
                    <button class="btn btn-info" onclick="highlightPrevious()" id="prevMatchBtn" style="display: none; font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;" title="前の検索結果へ">▲ 前へ</button>
                    <button class="btn btn-info" onclick="highlightNext()" id="nextMatchBtn" style="display: none; font-weight: 600; background: #3b82f6; border: 2px solid #2563eb; color: white;" title="次の検索結果へ">次へ ▼</button>
                </div>
                <span id="matchCounter" style="display: none; font-size: 10px; color: #666; text-align: center;"></span>
            </div>
        </div>
    </div>
    
    <div class="container">
        
        <div id="errorPanel" style="display: none; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 2px solid var(--warning-color); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 24px; box-shadow: var(--shadow-xl);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; color: #92400e; font-weight: 700; font-size: 16px; letter-spacing: 0.3px;">⚠️ 構文エラー・警告</h3>
                <button onclick="document.getElementById('errorPanel').style.display='none'" style="background: var(--warning-color); border: none; padding: 8px 16px; border-radius: var(--radius-md); cursor: pointer; color: white; font-weight: 600; transition: all var(--transition-base); box-shadow: var(--shadow-sm);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='var(--shadow-md)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='var(--shadow-sm)'">閉じる</button>
            </div>
            <div id="errorList"></div>
        </div>
        
        <div id="status" class="status"></div>
        
        <div class="editor-container">
            <div class="editor-panel" id="editorPanel">
                <div class="panel-resize-handle n"></div>
                <div class="panel-resize-handle s"></div>
                <div class="panel-resize-handle e"></div>
                <div class="panel-resize-handle w"></div>
                <div class="panel-resize-handle ne"></div>
                <div class="panel-resize-handle nw"></div>
                <div class="panel-resize-handle se"></div>
                <div class="panel-resize-handle sw"></div>
                <div class="panel-header">
                    <span>📄 HTMLソース</span>
                    <button class="btn-fullscreen" onclick="toggleFullscreen('editorPanel')" title="全画面表示" style="background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-left: 8px;">⛶</button>
                </div>
                <div class="editor-wrapper">
                    <textarea id="htmlEditor" class="editor" spellcheck="false" data-filename="{{ filename|e }}" data-has-content="{% if has_content %}true{% else %}false{% endif %}"></textarea>
                    <div id="editorHighlight" class="editor-highlight"></div>
                </div>
            </div>
            <div class="resizer" id="resizer"></div>
            <div class="editor-panel" id="previewPanel">
                <div class="panel-resize-handle n"></div>
                <div class="panel-resize-handle s"></div>
                <div class="panel-resize-handle e"></div>
                <div class="panel-resize-handle w"></div>
                <div class="panel-resize-handle ne"></div>
                <div class="panel-resize-handle nw"></div>
                <div class="panel-resize-handle se"></div>
                <div class="panel-resize-handle sw"></div>
                <div class="panel-header">
                    <span>👁️ プレビュー</span>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button class="btn-fullscreen" onclick="toggleFullscreen('previewPanel')" title="全画面表示" style="background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;">⛶</button>
                        <button class="btn btn-success" onclick="downloadPreview()" id="downloadPreviewBtn" style="font-size: 12px; padding: 6px 12px; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; font-weight: 600;" title="プレビューをHTMLファイルとしてダウンロード" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
                            ⬇️ HTMLとして保存
                        </button>
                    </div>
                </div>
                <iframe id="preview" class="preview" sandbox="allow-same-origin allow-scripts allow-forms allow-popups" title="HTMLプレビュー"></iframe>
            </div>
        </div>
        
        <div class="info-panel">
            <h3 style="margin-bottom: 20px; color: #2d3748;">📋 ファイル情報</h3>
            {% if filename %}
            <div class="info-item">
                <div class="info-label">ファイル名</div>
                <div class="info-value">{% if filename %}{{ filename }}{% else %}ファイル未選択{% endif %}</div>
            </div>
            <div class="info-item">
                <div class="info-label">ファイルサイズ</div>
                <div class="info-value">{{ file_size }} bytes</div>
            </div>
            <div class="info-item">
                <div class="info-label">リンク数</div>
                <div class="info-value">{{ links_count }}</div>
            </div>
            <div class="info-item">
                <div class="info-label">画像数</div>
                <div class="info-value">{{ images_count }}</div>
            </div>
            <div class="info-item">
                <div class="info-label">スクリプト数</div>
                <div class="info-value">{{ scripts_count }}</div>
            </div>
            {% endif %}
        </div>
    </div>
    
    <!-- 構造情報モーダル -->
    <div id="structureModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('structureModal')">&times;</span>
            <h2>📊 HTML構造情報</h2>
            <div id="structureInfo" style="margin-top: 20px;"></div>
        </div>
    </div>
    
    <!-- 検索モーダル -->
    <div id="searchModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('searchModal')">&times;</span>
            <h2>🔍 検索・置換</h2>
            <div class="form-group">
                <label class="form-label">検索文字列</label>
                <input type="text" id="searchText" class="form-input" placeholder="検索する文字列">
            </div>
            <div class="form-group">
                <label class="form-label">置換文字列</label>
                <input type="text" id="replaceText" class="form-input" placeholder="置換する文字列（空欄可）">
            </div>
            <button class="btn btn-primary" onclick="performSearchReplace()">検索・置換</button>
        </div>
    </div>

    <!-- 差分検出モーダル -->
    <div id="diffAnalysisModal" class="modal">
        <div class="modal-content" style="max-width: 1000px;">
            <span class="close" onclick="closeModal('diffAnalysisModal')">&times;</span>
            <h2>🔍 差分検出（27校の大学ホームページ）</h2>
            <p style="margin-top: 10px; color: #4a5568; line-height: 1.6;">
                指定されたディレクトリ内の27校のHTMLファイルを分析し、構造・スタイル・コンテンツ・属性の差分を検出します。
            </p>
            
            <div class="form-group" style="margin-top: 20px;">
                <label class="form-label">分析対象ディレクトリ</label>
                <input type="text" id="diffAnalysisDir" class="form-input" placeholder="例: /tmp/html または空欄でアップロードフォルダを使用" value="" title="空欄の場合はアップロードフォルダを使用" oninput="updateDiffAnalysisDirInfo()">
                <div id="diffAnalysisDirInfo" style="margin-top: 8px; padding: 8px; background: #f0f4f8; border-radius: 5px; border-left: 3px solid #667eea; display: none;">
                    <div style="font-size: 11px; color: #4a5568; font-weight: 600; margin-bottom: 4px;">📂 使用されるディレクトリ:</div>
                    <div id="diffAnalysisDirPath" style="font-size: 12px; color: #2d3748; font-family: monospace; font-weight: 500;"></div>
                    <div id="diffAnalysisDirFiles" style="font-size: 11px; color: #718096; margin-top: 4px;"></div>
                    <div id="diffAnalysisFileList" style="margin-top: 8px; max-height: 200px; overflow-y: auto; display: none;">
                        <div style="font-size: 11px; color: #4a5568; font-weight: 600; margin-bottom: 4px;">📄 分析対象のHTMLファイル:</div>
                        <div id="diffAnalysisFileListContent" style="font-size: 11px; color: #2d3748; font-family: monospace; line-height: 1.6;"></div>
                    </div>
                </div>
                <small style="color: #718096; font-size: 12px; display: block; margin-top: 8px;">
                    ※ ディレクトリ内のすべてのHTMLファイル（.html, .htm）を分析対象とします<br>
                    ※ 空欄の場合は、アップロードフォルダが使用されます
                </small>
            </div>
            
            <div class="form-group">
                <label class="form-label">検出オプション</label>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="diffOptionStructure" checked>
                        <span>HTML構造の差分（タグ、クラス、ID）</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="diffOptionStyles" checked>
                        <span>CSSスタイルの差分</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="diffOptionContent" checked>
                        <span>コンテンツ（テキスト）の差分</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="diffOptionAttributes" checked>
                        <span>属性の差分</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="diffOptionDetailed" checked>
                        <span>詳細な差分情報を表示</span>
                    </label>
                </div>
            </div>
            
            <div id="diffAnalysisProgress" style="display: none; margin-top: 15px; padding: 10px; background: #f0f4f8; border-radius: 5px;">
                <div style="font-size: 12px; color: #4a5568; margin-bottom: 5px;" id="diffProgressText">処理中...</div>
                <div style="background: #e2e8f0; border-radius: 3px; height: 20px; overflow: hidden;">
                    <div id="diffAnalysisProgressBar" style="background: #667eea; height: 100%; width: 0%; transition: width 0.3s;"></div>
                </div>
            </div>
            
            <div id="diffAnalysisResult" style="display: none; margin-top: 15px;">
                <div style="display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="downloadDiffReport()" id="downloadDiffBtn" style="font-size: 12px; padding: 8px 16px;">📥 差分レポートをダウンロード</button>
                    <button class="btn btn-info" onclick="exportDiffToCSV()" id="exportDiffCSVBtn" style="font-size: 12px; padding: 8px 16px;">📊 CSVでエクスポート</button>
                    <button class="btn btn-warning" onclick="generateGCDTemplate()" id="generateGCDBtn" style="font-size: 12px; padding: 8px 16px;">🔀 最大公約数テンプレート生成</button>
                </div>
                <div id="diffAnalysisResultContent" style="max-height: 500px; overflow-y: auto; padding: 15px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;"></div>
            </div>
            
            <div id="gcdTemplateResult" style="display: none; margin-top: 15px; padding: 15px; background: #f0f4f8; border-radius: 5px; max-height: 400px; overflow-y: auto;">
                <h3 style="font-size: 14px; margin-bottom: 10px;">最大公約数テンプレート生成結果</h3>
                <div id="gcdTemplateResultContent" style="font-size: 12px; line-height: 1.6;"></div>
                <div style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
                    <button class="btn btn-success" onclick="downloadGCDTemplate()" id="downloadGCDBtn" style="font-size: 12px; padding: 8px 16px;">⬇️ テンプレートをダウンロード</button>
                    <button class="btn btn-primary" onclick="generateUniversityPages()" id="generateUnivPagesBtn" style="font-size: 12px; padding: 8px 16px;">🏫 27大学のホームページを生成</button>
                </div>
            </div>
            
            <div id="universityPagesResult" style="display: none; margin-top: 15px; padding: 15px; background: #f0f4f8; border-radius: 5px; max-height: 400px; overflow-y: auto;">
                <h3 style="font-size: 14px; margin-bottom: 10px;">27大学のホームページ生成結果</h3>
                <div id="universityPagesResultContent" style="font-size: 12px; line-height: 1.6;"></div>
                <div style="display: flex; gap: 10px; margin-top: 15px;">
                    <button class="btn btn-success" onclick="downloadUniversityPages()" id="downloadUnivPagesBtn" style="font-size: 12px; padding: 8px 16px;">📦 ZIPファイルをダウンロード</button>
                </div>
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                <button class="btn btn-primary" onclick="performDiffAnalysis()" id="performDiffBtn">🔍 差分検出実行</button>
                <button class="btn" onclick="closeModal('diffAnalysisModal')" style="background: #e2e8f0; color: #4a5568;">キャンセル</button>
            </div>
        </div>
    </div>
    
    <!-- テンプレート統合モーダル -->
    <div id="templateMergeModal" class="modal">
        <div class="modal-content" style="max-width: 900px;">
            <span class="close" onclick="closeModal('templateMergeModal')">&times;</span>
            <h2>🔀 テンプレート統合（差分吸収）</h2>
            <p style="margin-top: 10px; color: #4a5568; line-height: 1.6;">
                複数のHTMLファイルを比較して、共通テンプレートを生成します。<br>
                各大学のカスタマイズによる差異を解消し、統一されたテンプレートを作成できます。
            </p>
            
            <div class="form-group" style="margin-top: 20px;">
                <label class="form-label">比較対象ディレクトリ</label>
                <div style="display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; align-items: center;">
                    <select id="templateMergeDirSelect" class="form-input" style="flex: 1; min-width: 200px; max-width: 300px;" onchange="onTemplateMergeDirSelect()" title="フォルダを選択">
                        <option value="">-- フォルダを選択 --</option>
                        <option value="__upload__">📁 アップロードフォルダ</option>
                    </select>
                    <input type="text" id="templateMergeDir" class="form-input" placeholder="または直接パスを入力: C:\html" style="flex: 1; min-width: 200px;" title="Windows: C:\\html または C:/html&#10;空欄の場合はアップロードフォルダを表示" list="templateMergeDirHistory">
                    <datalist id="templateMergeDirHistory"></datalist>
                    <button class="btn btn-info" onclick="loadTemplateFileList()" style="white-space: nowrap;">📁 ファイル読み込み</button>
                </div>
                <div id="templateMergeCurrentDir" style="margin-bottom: 10px; padding: 12px; background: #f0f4f8; border-radius: 5px; border-left: 3px solid #667eea;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <div style="flex: 1;">
                            <div style="font-size: 11px; color: #718096; margin-bottom: 4px;">📂 現在の検索フォルダ</div>
                            <div id="templateMergeCurrentDirPath" style="font-size: 13px; color: #2d3748; font-family: monospace; font-weight: 500; word-break: break-all;"></div>
                        </div>
                        <button class="btn" onclick="selectTemplateMergeDir()" style="font-size: 11px; padding: 6px 12px; background: #e2e8f0; color: #4a5568; border: none; border-radius: 4px; cursor: pointer; white-space: nowrap;" title="別のフォルダを選択">🔄 変更</button>
                    </div>
                </div>
                <small style="color: #718096; font-size: 12px; display: block; margin-bottom: 10px;">
                    ドロップダウンから選択するか、直接パスを入力してください。空欄の場合はアップロードフォルダが使用されます。
                </small>
            </div>
            
            <div class="form-group">
                <label class="form-label">比較するファイル（複数選択可）</label>
                <div id="templateFileList" style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 5px; padding: 10px;">
                    <p style="color: #718096; font-size: 12px; margin: 0;">ファイル一覧を読み込み中...</p>
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">統合オプション</label>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="mergeOptionStructure" checked>
                        <span>HTML構造を統合（タグ、クラス、ID）</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="mergeOptionStyles" checked>
                        <span>CSSスタイルを統合</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="mergeOptionContent" checked>
                        <span>コンテンツ（テキスト）を統合（共通部分のみ）</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="mergeOptionAttributes" checked>
                        <span>属性を統合（共通属性のみ）</span>
                    </label>
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">差異の扱い</label>
                <select id="mergeDiffHandling" class="form-input">
                    <option value="common" selected>共通部分のみ採用（差異は削除）</option>
                    <option value="first">最初のファイルを基準（他の差異は無視）</option>
                    <option value="comment">差異をコメントとして残す</option>
                </select>
            </div>
            
            <div id="templateMergeProgress" style="display: none; margin-top: 15px; padding: 10px; background: #f0f4f8; border-radius: 5px;">
                <div style="font-size: 12px; color: #4a5568; margin-bottom: 5px;">処理中...</div>
                <div style="background: #e2e8f0; border-radius: 3px; height: 20px; overflow: hidden;">
                    <div id="templateMergeProgressBar" style="background: #667eea; height: 100%; width: 0%; transition: width 0.3s;"></div>
                </div>
            </div>
            
            <div id="templateMergeResult" style="display: none; margin-top: 15px; padding: 15px; background: #f0f4f8; border-radius: 5px; max-height: 300px; overflow-y: auto;">
                <h3 style="font-size: 14px; margin-bottom: 10px;">統合結果</h3>
                <div id="templateMergeResultContent" style="font-size: 12px; line-height: 1.6;"></div>
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                <button class="btn btn-primary" onclick="performTemplateMerge()" id="performMergeBtn">🔀 統合実行</button>
                <button class="btn btn-success" onclick="downloadMergedTemplate()" id="downloadMergedBtn" style="display: none;">⬇️ 統合テンプレートをダウンロード</button>
                <button class="btn" onclick="closeModal('templateMergeModal')" style="background: #e2e8f0; color: #4a5568;">キャンセル</button>
            </div>
        </div>
    </div>
    
    <!-- 大学データ管理モーダル -->
    <div id="universityDataModal" class="modal">
        <div class="modal-content" style="max-width: 1000px;">
            <span class="close" onclick="closeModal('universityDataModal')">&times;</span>
            <h2>🏫 大学データ管理（27大学の入学手続きページ）</h2>
            <p style="margin-top: 10px; color: #4a5568; line-height: 1.6;">
                各大学のページデータを管理し、共通テンプレートと統合してページを生成します。<br>
                ①大学毎のデータ内容の違いはDBで管理、②項目の表示位置はJSONファイルで管理します。
            </p>
            
            <div style="display: flex; gap: 20px; margin-top: 20px;">
                <!-- 左側: 大学一覧 -->
                <div style="flex: 1; min-width: 250px;">
                    <div class="form-group">
                        <label class="form-label">大学一覧</label>
                        <div style="display: flex; gap: 8px; margin-bottom: 10px;">
                            <input type="text" id="newUniversityCode" class="form-input" placeholder="大学コード" style="flex: 1;">
                            <input type="text" id="newUniversityName" class="form-input" placeholder="大学名" style="flex: 2;">
                            <button class="btn btn-primary" onclick="addUniversity()" style="white-space: nowrap;">追加</button>
                        </div>
                        <div id="universityList" style="max-height: 400px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 5px; padding: 10px;">
                            <p style="color: #718096; font-size: 12px; margin: 0;">読み込み中...</p>
                        </div>
                    </div>
                </div>
                
                <!-- 右側: ページデータ管理 -->
                <div style="flex: 2; min-width: 400px;">
                    <div class="form-group">
                        <label class="form-label">ページタイトル</label>
                        <select id="pageTitleSelect" class="form-input" onchange="loadUniversityPageData()">
                            <option value="">-- ページを選択 --</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">ページ内容</label>
                        <textarea id="pageContentEditor" class="form-input" rows="10" placeholder="ページのHTMLコンテンツを入力"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">メタデータ（JSON形式）</label>
                        <textarea id="pageMetadataEditor" class="form-input" rows="5" placeholder='{"key": "value"}'></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <button class="btn btn-primary" onclick="saveUniversityPageData()">💾 保存</button>
                        <button class="btn btn-info" onclick="loadUniversityConfig()">⚙️ 表示位置設定</button>
                        <button class="btn btn-success" onclick="generateUniversityPage()">🔀 ページ生成</button>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 20px; background: #f0f4f8; border-radius: 8px; border: 2px solid #667eea;">
                        <h3 style="font-size: 16px; margin-bottom: 15px; color: #2d3748;">📄 YAML設定ファイルから一括生成</h3>
                        <p style="font-size: 12px; color: #4a5568; margin-bottom: 15px;">
                            university_pages_config.ymlを基に、指定した大学または全大学の入学手続きWEBページを一括生成します。
                        </p>
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label class="form-label">対象大学（空欄の場合は全大学）</label>
                            <input type="text" id="yamlUniversityCodes" class="form-input" placeholder="例: UNIV001,UNIV002 または空欄で全大学" style="width: 100%;">
                            <small style="color: #718096; font-size: 11px;">カンマ区切りで大学コードを指定（例: UNIV001,UNIV002）</small>
                        </div>
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label class="form-label">出力ディレクトリ（空欄の場合はデフォルト）</label>
                            <input type="text" id="yamlOutputDirectory" class="form-input" placeholder="例: C:\output\pages または空欄" style="width: 100%;">
                        </div>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-warning" onclick="generatePagesFromYAML()" style="font-weight: 600;">🚀 ページ一括生成</button>
                            <button class="btn btn-success" onclick="downloadGeneratedPagesFromYAML()" style="font-weight: 600;">📦 生成済みページをダウンロード</button>
                        </div>
                        <div id="yamlGenerationResult" style="display: none; margin-top: 15px; padding: 15px; background: white; border-radius: 5px; border: 1px solid #e2e8f0;">
                            <div id="yamlGenerationResultContent" style="font-size: 12px; line-height: 1.6;"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 表示位置設定モーダル（サブモーダル） -->
            <div id="universityConfigModal" style="display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); z-index: 10001; max-width: 900px; width: 90%; max-height: 90vh; overflow-y: auto;">
                <h3 style="margin-top: 0;">⚙️ 出力項目の表示位置・属性設定</h3>
                <p style="font-size: 12px; color: #718096; margin-bottom: 15px;">
                    各出力項目の表示位置、スタイル、表示/非表示などの属性をJSON形式で管理します。
                </p>
                
                <!-- タブ切り替え -->
                <div style="display: flex; gap: 10px; margin-bottom: 15px; border-bottom: 2px solid #e2e8f0;">
                    <button class="btn" id="configTabItems" onclick="switchConfigTab('items')" style="background: #667eea; color: white; border: none; padding: 8px 16px; border-radius: 4px 4px 0 0; cursor: pointer;">項目属性</button>
                    <button class="btn" id="configTabLayout" onclick="switchConfigTab('layout')" style="background: #e2e8f0; color: #4a5568; border: none; padding: 8px 16px; border-radius: 4px 4px 0 0; cursor: pointer;">レイアウト設定</button>
                    <button class="btn" id="configTabRaw" onclick="switchConfigTab('raw')" style="background: #e2e8f0; color: #4a5568; border: none; padding: 8px 16px; border-radius: 4px 4px 0 0; cursor: pointer;">JSON編集</button>
                </div>
                
                <!-- 項目属性タブ -->
                <div id="configTabItemsContent" style="display: block;">
                    <div style="margin-bottom: 15px;">
                        <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                            <input type="text" id="newItemId" class="form-input" placeholder="項目ID" style="flex: 1;">
                            <button class="btn btn-primary" onclick="addConfigItem()" style="white-space: nowrap;">項目を追加</button>
                        </div>
                        <div id="configItemsList" style="max-height: 400px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 5px; padding: 10px;">
                            <p style="color: #718096; font-size: 12px; margin: 0;">項目がありません</p>
                        </div>
                    </div>
                </div>
                
                <!-- レイアウト設定タブ -->
                <div id="configTabLayoutContent" style="display: none;">
                    <div class="form-group">
                        <label class="form-label">表示順序（クラス名の配列）</label>
                        <textarea id="displayOrderEditor" class="form-input" rows="5" placeholder='["section1", "section2", "section3"]' style="font-family: monospace; font-size: 12px;"></textarea>
                    </div>
                </div>
                
                <!-- JSON編集タブ -->
                <div id="configTabRawContent" style="display: none;">
                    <div class="form-group">
                        <label class="form-label">JSON設定（完全編集）</label>
                        <textarea id="universityConfigEditor" class="form-input" rows="20" style="font-family: monospace; font-size: 12px;" placeholder='{"layout": {}, "display_order": [], "items": {}}'></textarea>
                        <small style="color: #718096; font-size: 11px; display: block; margin-top: 5px;">
                            JSON形式の例:<br>
                            {<br>
                            &nbsp;&nbsp;"items": {<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;"item_id": {<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"id": "element_id",<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"class": "element-class",<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"visible": true,<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"order": 1,<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"styles": {"margin-top": "20px", "color": "#333"},<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"add_classes": ["new-class"],<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"attributes": {"data-id": "123"}<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;}<br>
                            &nbsp;&nbsp;},<br>
                            &nbsp;&nbsp;"display_order": ["section1", "section2"]<br>
                            }
                        </small>
                    </div>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 15px; justify-content: flex-end;">
                    <button class="btn btn-primary" onclick="saveUniversityConfig()">保存</button>
                    <button class="btn" onclick="closeUniversityConfigModal()" style="background: #e2e8f0; color: #4a5568;">キャンセル</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- デザイン出力モーダル -->
    <div id="designExportModal" class="modal">
        <div class="modal-content" style="max-width: 720px;">
            <span class="close" onclick="closeModal('designExportModal')">&times;</span>
            <h2>📤 デザイン出力（差異確認用）</h2>
            <p style="margin-top: 10px; color: #4a5568; line-height: 1.6;">
                プレビュー上の要素の主要スタイル（computed style）を出力します。<br>
                2つのHTMLで出力したファイルをDiffツールやExcelで比較してください。
            </p>
            <div class="form-group" style="margin-top: 20px;">
                <label class="form-label">出力形式</label>
                <select id="designExportFormat" class="form-input">
                    <option value="json" selected>JSON（Diff向け）</option>
                    <option value="csv">CSV（Excel向け）</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">対象（絞り込み）</label>
                <select id="designExportScope" class="form-input">
                    <option value="all" selected>すべて（body配下）</option>
                    <option value="form">フォーム要素のみ（label/input/select/textarea/button）</option>
                    <option value="label">ラベル周り（label と for/隣接要素）</option>
                </select>
                <small style="color: #718096; font-size: 12px; display: block; margin-top: 8px;">
                    ※ 要素数が多いページは自動的に上限を設けます。
                </small>
            </div>
            <div class="form-group">
                <label class="form-label">最大要素数</label>
                <input type="number" id="designExportMaxNodes" class="form-input" value="3000" min="100" max="20000">
            </div>
            <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                <button class="btn btn-primary" onclick="performDesignExport()">出力</button>
                <button class="btn" onclick="closeModal('designExportModal')" style="background: #e2e8f0; color: #4a5568;">キャンセル</button>
            </div>
        </div>
    </div>
    
    <!-- 画面比較モーダル -->
    <div id="screenComparisonModal" class="modal">
        <div class="modal-content" style="max-width: 95vw; width: 95vw; height: 95vh; max-height: 95vh; display: flex; flex-direction: column;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-shrink: 0;">
                <div>
                    <h2 style="margin: 0;">🖼️ 画面比較（最大27大学）</h2>
                    <p style="margin: 5px 0 0 0; font-size: 12px; color: #718096;">HTMLファイルとCSSファイルを比較・編集できます</p>
                </div>
                <span class="close" onclick="closeModal('screenComparisonModal')">&times;</span>
            </div>
            
            <div style="display: flex; gap: 15px; margin-bottom: 15px; flex-shrink: 0; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 300px;">
                    <label class="form-label">比較対象ディレクトリ</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="comparisonDir" class="form-input" placeholder="例: C:\\html または C:/html (絶対パスを指定)" style="flex: 1;" title="Windows: C:\\html または C:/html&#10;Linux/Mac: /path/to/html">
                        <button class="btn btn-info" onclick="loadComparisonFiles()" style="white-space: nowrap;">📁 ファイル読み込み</button>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; align-items: flex-end;">
                    <select id="comparisonLayout" class="form-input" style="width: 150px;" onchange="updateComparisonLayout()">
                        <option value="grid">グリッド表示</option>
                        <option value="horizontal">横並び</option>
                        <option value="vertical">縦並び</option>
                    </select>
                    <button class="btn btn-primary" onclick="toggleComparisonMode()" id="comparisonModeBtn">比較モード</button>
                    <button class="btn btn-success" onclick="exportComparisonReport()" id="exportComparisonBtn">📊 比較レポート出力</button>
                </div>
            </div>
            
            <div style="margin-bottom: 15px; flex-shrink: 0;">
                <div style="display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 200px;">
                        <input type="text" id="fileSearchInput" class="form-input" placeholder="🔍 ファイル名で検索..." style="font-size: 12px; padding: 6px 10px;" oninput="filterComparisonFiles()">
                    </div>
                    <select id="fileTypeFilter" class="form-input" style="width: 120px; font-size: 12px; padding: 6px 10px;" onchange="filterComparisonFiles()">
                        <option value="all">すべて</option>
                        <option value="html">HTMLのみ</option>
                        <option value="css">CSSのみ</option>
                    </select>
                    <select id="fileSortOption" class="form-input" style="width: 120px; font-size: 12px; padding: 6px 10px;" onchange="sortComparisonFiles()">
                        <option value="name">名前順</option>
                        <option value="size">サイズ順</option>
                        <option value="type">タイプ順</option>
                    </select>
                </div>
                <div id="comparisonFileList" style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 5px; padding: 10px; background: #f8fafc;">
                    <p style="color: #718096; font-size: 12px; margin: 0; text-align: center;">ディレクトリを指定してファイルを読み込んでください</p>
                </div>
            </div>
            
            <div id="comparisonContainer" style="flex: 1; overflow: auto; background: #f1f5f9; border-radius: 8px; padding: 15px; position: relative;">
                <div id="comparisonGrid" style="display: grid; gap: 15px; min-height: 100%;"></div>
            </div>
        </div>
    </div>
    
    <!-- アップロードモーダル -->
    <div id="uploadModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('uploadModal')">&times;</span>
            <h2 style="margin-bottom: 20px;">📤 HTMLファイルをアップロード</h2>
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label class="form-label">HTMLファイルを選択</label>
                    <div id="dropZone" style="border: 2px dashed #cbd5e0; border-radius: 8px; padding: 30px; text-align: center; background: #f7fafc; margin-bottom: 15px; transition: all 0.3s;">
                        <input type="file" id="fileInput" name="file" accept=".html,.htm" class="form-input" required 
                               style="display: none;" onchange="updateFileName()">
                        <label for="fileInput" style="cursor: pointer; display: inline-block;">
                            <div style="font-size: 48px; margin-bottom: 10px;">📄</div>
                            <div style="font-weight: 600; color: #2d3748; margin-bottom: 5px;">クリックしてファイルを選択</div>
                            <div style="font-size: 12px; color: #718096;">またはドラッグ&ドロップ</div>
                        </label>
                        <div id="fileName" style="margin-top: 15px; font-size: 14px; color: #4299e1; font-weight: 500; display: none;"></div>
                    </div>
                    <small style="color: #718096; font-size: 12px; display: block; margin-top: 10px;">
                        ✓ HTMLファイル（.html, .htm）のみアップロード可能です<br>
                        ✓ 最大ファイルサイズ: 50MB
                    </small>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="submit" class="btn btn-primary" style="flex: 1; padding: 12px;">アップロードして編集開始</button>
                    <button type="button" class="btn" onclick="closeModal('uploadModal')" style="background: #e2e8f0; color: #4a5568;">キャンセル</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- ファイル一覧モーダル -->
    <div id="fileListModal" class="modal">
        <div class="modal-content" style="max-width: 900px;">
            <span class="close" onclick="closeModal('fileListModal')">&times;</span>
            <h2>📁 ファイル一覧</h2>
            
            <div style="margin-top: 20px; margin-bottom: 15px;">
                <div style="display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 300px;">
                        <label class="form-label">ディレクトリパス（空欄の場合はアップロードフォルダ）</label>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="fileListDir" class="form-input" placeholder="例: C:\html または空欄でアップロードフォルダ" style="flex: 1;" title="Windows: C:\\html または C:/html&#10;空欄の場合はアップロードフォルダを表示">
                            <button class="btn btn-info" onclick="loadDirectoryFiles()" style="white-space: nowrap;">📁 読み込み</button>
                        </div>
                    </div>
                    <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                        <select id="fileListTypeFilter" class="form-input" style="width: 120px; font-size: 12px; padding: 6px 10px;" onchange="filterFileList()">
                            <option value="all">すべて</option>
                            <option value="html">HTML</option>
                            <option value="css">CSS</option>
                            <option value="other">その他</option>
                        </select>
                        <input type="text" id="fileListSearch" class="form-input" placeholder="🔍 ファイル名で検索..." style="width: 150px; font-size: 12px; padding: 6px 10px;" oninput="filterFileList()" title="ファイル名で検索">
                        <input type="text" id="fileListIdentifierSearch" class="form-input" placeholder="🏷️ ID/クラスで検索..." style="width: 180px; font-size: 12px; padding: 6px 10px;" oninput="filterFileList()" title="HTMLファイル内のID、クラス名、data属性で検索">
                    </div>
                </div>
            </div>
            
            <div id="fileListContent" style="margin-top: 20px;">
                <p style="text-align: center; padding: 40px; color: #718096;">ディレクトリを指定してファイルを読み込んでください</p>
            </div>
        </div>
    </div>
    
    <script>
        // エディタ要素を取得するヘルパー関数
        function getEditor() {
            if (!window.editor) {
                window.editor = document.getElementById('htmlEditor');
            }
            return window.editor;
        }
        
        // DOMContentLoaded後に初期化
        document.addEventListener('DOMContentLoaded', function() {
            const editor = document.getElementById('htmlEditor');
            const preview = document.getElementById('preview');
            // data属性から設定を取得
            const hasContent = editor && editor.dataset.hasContent === 'true';
            const filename = editor ? editor.dataset.filename || '' : '';
            
            // グローバル変数として設定（他の関数で使用可能）
            window.editorFilename = filename;
            window.editor = editor;  // エディタ要素をグローバル変数として保存
            
            // 念のため、window.onloadでも再設定
            window.addEventListener('load', function() {
                if (!window.editor) {
                    window.editor = document.getElementById('htmlEditor');
                }
            });
            
            // 環境変数から設定を読み込んでプレースホルダーを更新
            loadConfigAndUpdatePlaceholders();
            
            // HTMLコンテンツをAJAXで取得
            if (editor && hasContent) {
                fetch('/content')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.content) {
                            editor.value = data.content;
                            updatePreview();
                        }
                    })
                    .catch(error => {
                        console.error('HTMLコンテンツの読み込みエラー:', error);
                    });
            }
            
            // リモコン盤の初期化
            initRemoteControl();
            
            // 利用手順パネルの初期化
            initUsageGuide();
            
            // トグルボタンのイベントリスナーを設定
            setupToggleButtons();
            
            // テンプレート統合の状態保存イベントリスナーを設定
            setupTemplateMergeStateSaving();
            
            // 画面比較の状態保存イベントリスナーを設定
            setupScreenComparisonStateSaving();
            
            // リサイザーの実装
            const resizer = document.getElementById('resizer');
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            const editorContainer = document.querySelector('.editor-container');
            
            if (resizer && editorPanel && previewPanel && editorContainer) {
                let isResizing = false;
                let startX = 1;
                let startEditorWidth = 1;
                
                resizer.addEventListener('mousedown', function(e) {
                    isResizing = true;
                    startX = e.clientX;
                    startEditorWidth = editorPanel.offsetWidth;
                    resizer.classList.add('resizing');
                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';
                    e.preventDefault();
                });
                
                document.addEventListener('mousemove', function(e) {
                    if (!isResizing) return;
                    
                    const diff = e.clientX - startX;
                    const containerWidth = editorContainer.offsetWidth;
                    const resizerWidth = resizer.offsetWidth;
                    const newEditorWidth = startEditorWidth + diff;
                    const minWidth = 201;
                    const maxWidth = containerWidth - resizerWidth - minWidth;
                    
                    if (newEditorWidth >= minWidth && newEditorWidth <= maxWidth) {
                        editorPanel.style.flex = `1 0 ${newEditorWidth}px`;
                        previewPanel.style.flex = '2 1 auto';
                    }
                });
                
                document.addEventListener('mouseup', function() {
                    if (isResizing) {
                        isResizing = false;
                        resizer.classList.remove('resizing');
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                    }
                });
            }
            
            // 通常モードでのパネルリサイズ機能の初期化
            initPanelResize();
            
            // 自由配置モードの初期化
            initFreeMode();
            
            // エディタの変更をプレビューに反映
            if (editor && preview) {
                editor.addEventListener('input', function() {
                    updatePreview();
                    // 検索結果がある場合はハイライトを更新
                    if (window.searchMatches && window.searchMatches.length > 1) {
                        const query = document.getElementById('searchBox')?.value.trim();
                        if (query) {
                            window.searchMatches = highlightInSource(query);
                            highlightAllMatches(window.searchMatches);
                        }
                    }
                });
                
                // カーソル位置に基づいてプレビュー内の要素をハイライト
                let highlightTimeout;
                function updatePreviewHighlight() {
                    clearTimeout(highlightTimeout);
                    highlightTimeout = setTimeout(function() {
                        highlightPreviewElement();
                    }, 151);
                }
                
                editor.addEventListener('keyup', updatePreviewHighlight);
                editor.addEventListener('mouseup', updatePreviewHighlight);
                editor.addEventListener('click', updatePreviewHighlight);
                
                // 選択範囲変更時もハイライト更新
                document.addEventListener('selectionchange', function() {
                    if (document.activeElement === editor) {
                        updatePreviewHighlight();
                    }
                });
            }
            
            // エディタのスクロールに合わせてハイライトもスクロール
            if (editor) {
                const highlightDiv = document.getElementById('editorHighlight');
                if (highlightDiv) {
                    // グローバル関数を使用
                    if (!window.syncHighlightScroll) {
                        window.syncHighlightScroll = function() {
                            const ed = getEditor();
                            const hd = document.getElementById('editorHighlight');
                            if (hd && ed) {
                                hd.scrollTop = ed.scrollTop;
                                hd.scrollLeft = ed.scrollLeft;
                            }
                        };
                    }
                    editor.addEventListener('scroll', window.syncHighlightScroll, { passive: true });
                }
            }
        });
        
        // 自由配置モードの実装
        let freeMode = false;
        let draggingPanel = null;
        let resizingPanel = null;
        let resizeDirection = '';
        let dragStartX = 0;
        let dragStartY = 0;
        let panelStartX = 0;
        let panelStartY = 0;
        let panelStartWidth = 0;
        let panelStartHeight = 0;
        
        function initPanelResize() {
            // 通常モードでのパネルリサイズ機能
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            const editorContainer = document.querySelector('.editor-container');
            
            if (!editorPanel || !previewPanel || !editorContainer) return;
            
            // 各パネルにリサイズ機能を追加
            [editorPanel, previewPanel].forEach(panel => {
                const handles = panel.querySelectorAll('.panel-resize-handle');
                handles.forEach(handle => {
                    handle.addEventListener('mousedown', function(e) {
                        // 自由配置モードの場合は無効
                        if (editorContainer.classList.contains('free-mode')) return;
                        
                        e.preventDefault();
                        e.stopPropagation();
                        
                        const direction = handle.className.split(' ').find(c => c !== 'panel-resize-handle' && c !== 'resizing');
                        if (!direction) return;
                        
                        const containerRect = editorContainer.getBoundingClientRect();
                        const panelRect = panel.getBoundingClientRect();
                        const otherPanel = panel === editorPanel ? previewPanel : editorPanel;
                        
                        let startX = e.clientX;
                        let startY = e.clientY;
                        let startWidth = panelRect.width;
                        let startHeight = panelRect.height;
                        let startLeft = panelRect.left - containerRect.left;
                        let startTop = panelRect.top - containerRect.top;
                        let startOtherWidth = otherPanel.offsetWidth;
                        
                        panel.classList.add('resizing');
                        handle.classList.add('resizing');
                        document.body.style.cursor = getComputedStyle(handle).cursor;
                        document.body.style.userSelect = 'none';
                        
                        function onMouseMove(e) {
                            const diffX = e.clientX - startX;
                            const diffY = e.clientY - startY;
                            
                            let newWidth = startWidth;
                            let newHeight = startHeight;
                            let newLeft = startLeft;
                            let newTop = startTop;
                            
                            // 方向に応じてサイズを調整
                            if (direction.includes('e')) {
                                newWidth = startWidth + diffX;
                            }
                            if (direction.includes('w')) {
                                newWidth = startWidth - diffX;
                                newLeft = startLeft + diffX;
                            }
                            if (direction.includes('s')) {
                                newHeight = startHeight + diffY;
                            }
                            if (direction.includes('n')) {
                                newHeight = startHeight - diffY;
                                newTop = startTop + diffY;
                            }
                            
                            // 最小サイズ制限
                            const minWidth = 200;
                            const minHeight = 200;
                            
                            if (newWidth < minWidth) {
                                if (direction.includes('w')) {
                                    newLeft = startLeft + startWidth - minWidth;
                                }
                                newWidth = minWidth;
                            }
                            if (newHeight < minHeight) {
                                if (direction.includes('n')) {
                                    newTop = startTop + startHeight - minHeight;
                                }
                                newHeight = minHeight;
                            }
                            
                            // コンテナ内に制限
                            const maxWidth = containerRect.width - (panel === editorPanel ? 6 : 0) - (panel === previewPanel ? 6 : 0) - minWidth;
                            const maxHeight = containerRect.height;
                            
                            if (newWidth > maxWidth) {
                                newWidth = maxWidth;
                                if (direction.includes('w')) {
                                    newLeft = containerRect.width - maxWidth - (panel === editorPanel ? 6 : 0);
                                }
                            }
                            if (newHeight > maxHeight) {
                                newHeight = maxHeight;
                                if (direction.includes('n')) {
                                    newTop = 0;
                                }
                            }
                            
                            // 横方向のリサイズ（左右のパネル間）
                            if (direction.includes('e') || direction.includes('w')) {
                                // パネルの幅を直接設定（flexを無効化）
                                panel.style.flex = `0 0 ${newWidth}px`;
                                panel.style.width = `${newWidth}px`;
                                
                                // もう一方のパネルも調整
                                const remainingWidth = containerRect.width - newWidth - 6; // 6pxはresizerの幅
                                if (remainingWidth >= minWidth) {
                                    otherPanel.style.flex = `1 1 ${remainingWidth}px`;
                                }
                            }
                            
                            // 縦方向のリサイズ
                            if (direction.includes('n') || direction.includes('s')) {
                                panel.style.height = `${newHeight}px`;
                                panel.style.minHeight = `${newHeight}px`;
                                
                                // エディタ/プレビューの高さも調整
                                const headerHeight = panel.querySelector('.panel-header')?.offsetHeight || 60;
                                const contentHeight = newHeight - headerHeight;
                                
                                if (panel === editorPanel) {
                                    const editorWrapper = panel.querySelector('.editor-wrapper');
                                    if (editorWrapper) {
                                        editorWrapper.style.height = `${contentHeight}px`;
                                    }
                                } else {
                                    const preview = panel.querySelector('.preview');
                                    if (preview) {
                                        preview.style.height = `${contentHeight}px`;
                                    }
                                }
                            }
                        }
                        
                        function onMouseUp() {
                            panel.classList.remove('resizing');
                            handle.classList.remove('resizing');
                            document.body.style.cursor = '';
                            document.body.style.userSelect = '';
                            document.removeEventListener('mousemove', onMouseMove);
                            document.removeEventListener('mouseup', onMouseUp);
                            
                            // サイズを保存
                            const panelId = panel.id;
                            const savedSize = {
                                width: panel.offsetWidth,
                                height: panel.offsetHeight
                            };
                            localStorage.setItem(`htmlEditor_${panelId}_size`, JSON.stringify(savedSize));
                        }
                        
                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                    });
                });
            });
            
            // 保存されたサイズを復元
            [editorPanel, previewPanel].forEach(panel => {
                const panelId = panel.id;
                const savedSize = localStorage.getItem(`htmlEditor_${panelId}_size`);
                if (savedSize) {
                    try {
                        const size = JSON.parse(savedSize);
                        if (size.width && size.width >= 200) {
                            panel.style.flex = `0 0 ${size.width}px`;
                            panel.style.width = `${size.width}px`;
                        }
                        if (size.height && size.height >= 200) {
                            panel.style.height = `${size.height}px`;
                            panel.style.minHeight = `${size.height}px`;
                            
                            const headerHeight = panel.querySelector('.panel-header')?.offsetHeight || 60;
                            const contentHeight = size.height - headerHeight;
                            
                            if (panel === editorPanel) {
                                const editorWrapper = panel.querySelector('.editor-wrapper');
                                if (editorWrapper) {
                                    editorWrapper.style.height = `${contentHeight}px`;
                                }
                            } else {
                                const preview = panel.querySelector('.preview');
                                if (preview) {
                                    preview.style.height = `${contentHeight}px`;
                                }
                            }
                        }
                    } catch (e) {
                        console.error('Failed to restore panel size:', e);
                    }
                }
            });
        }
        
        function initFreeMode() {
            // 保存された状態を復元
            const savedMode = localStorage.getItem('htmlEditor_freeMode');
            if (savedMode === 'true') {
                toggleFreeMode(true);
            } else {
                restorePanelPositions();
            }
        }
        
        function toggleFreeMode(forceState) {
            const editorContainer = document.querySelector('.editor-container');
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            const freeModeBtn = document.getElementById('freeModeBtn');
            
            if (forceState !== undefined) {
                freeMode = forceState;
            } else {
                freeMode = !freeMode;
            }
            
            if (freeMode) {
                editorContainer.classList.add('free-mode');
                freeModeBtn.textContent = '📐 通常モード';
                freeModeBtn.title = '通常の分割表示モードに戻します';
                
                // パネルを絶対配置に変更
                if (editorPanel && previewPanel) {
                    const containerRect = editorContainer.getBoundingClientRect();
                    
                    // 保存された位置を復元、なければデフォルト位置
                    const editorPos = loadPanelPosition('editorPanel');
                    const previewPos = loadPanelPosition('previewPanel');
                    
                    if (!editorPos) {
                        setPanelPosition(editorPanel, 0, 0, containerRect.width / 2 - 3, containerRect.height);
                    } else {
                        setPanelPosition(editorPanel, editorPos.x, editorPos.y, editorPos.width, editorPos.height);
                    }
                    
                    if (!previewPos) {
                        setPanelPosition(previewPanel, containerRect.width / 2 + 3, 0, containerRect.width / 2 - 3, containerRect.height);
                    } else {
                        setPanelPosition(previewPanel, previewPos.x, previewPos.y, previewPos.width, previewPos.height);
                    }
                    
                    // リサイズハンドルを追加
                    addResizeHandles(editorPanel);
                    addResizeHandles(previewPanel);
                    
                    // ドラッグ機能を有効化
                    enableDrag(editorPanel);
                    enableDrag(previewPanel);
                    
                    // 高さを調整
                    updatePanelContentHeight(editorPanel);
                    updatePanelContentHeight(previewPanel);
                }
            } else {
                editorContainer.classList.remove('free-mode');
                freeModeBtn.textContent = '🪟 自由配置モード';
                freeModeBtn.title = 'ウィンドウを自由に移動・リサイズできるモードに切り替えます';
                
                // パネルを通常のflex配置に戻す
                if (editorPanel && previewPanel) {
                    editorPanel.style.position = '';
                    editorPanel.style.left = '';
                    editorPanel.style.top = '';
                    editorPanel.style.width = '';
                    editorPanel.style.height = '';
                    previewPanel.style.position = '';
                    previewPanel.style.left = '';
                    previewPanel.style.top = '';
                    previewPanel.style.width = '';
                    previewPanel.style.height = '';
                    
                    // リサイズハンドルを削除
                    removeResizeHandles(editorPanel);
                    removeResizeHandles(previewPanel);
                }
            }
            
            localStorage.setItem('htmlEditor_freeMode', freeMode.toString());
        }
        
        function setPanelPosition(panel, x, y, width, height) {
            panel.style.position = 'absolute';
            panel.style.left = x + 'px';
            panel.style.top = y + 'px';
            panel.style.width = width + 'px';
            panel.style.height = height + 'px';
        }
        
        function loadPanelPosition(panelId) {
            const saved = localStorage.getItem(`htmlEditor_${panelId}_position`);
            if (saved) {
                try {
                    return JSON.parse(saved);
                } catch (e) {
                    return null;
                }
            }
            return null;
        }
        
        function savePanelPosition(panelId, x, y, width, height) {
            localStorage.setItem(`htmlEditor_${panelId}_position`, JSON.stringify({ x, y, width, height }));
        }
        
        function restorePanelPositions() {
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            
            if (editorPanel) {
                const pos = loadPanelPosition('editorPanel');
                if (pos) {
                    setPanelPosition(editorPanel, pos.x, pos.y, pos.width, pos.height);
                }
            }
            
            if (previewPanel) {
                const pos = loadPanelPosition('previewPanel');
                if (pos) {
                    setPanelPosition(previewPanel, pos.x, pos.y, pos.width, pos.height);
                }
            }
        }
        
        function enableDrag(panel) {
            const header = panel.querySelector('.panel-header');
            if (!header) return;
            
            header.addEventListener('mousedown', function(e) {
                if (!freeMode) return;
                if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
                
                draggingPanel = panel;
                header.classList.add('dragging');
                panel.classList.add('dragging');
                
                const rect = panel.getBoundingClientRect();
                const containerRect = panel.parentElement.getBoundingClientRect();
                
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                panelStartX = rect.left - containerRect.left;
                panelStartY = rect.top - containerRect.top;
                
                e.preventDefault();
            });
        }
        
        function addResizeHandles(panel) {
            if (panel.querySelector('.resize-handle')) return; // 既に追加済み
            
            const handles = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];
            handles.forEach(direction => {
                const handle = document.createElement('div');
                handle.className = `resize-handle ${direction}`;
                handle.addEventListener('mousedown', function(e) {
                    if (!freeMode) return;
                    
                    resizingPanel = panel;
                    resizeDirection = direction;
                    panel.classList.add('resizing');
                    handle.classList.add('resizing');
                    
                    const rect = panel.getBoundingClientRect();
                    const containerRect = panel.parentElement.getBoundingClientRect();
                    
                    dragStartX = e.clientX;
                    dragStartY = e.clientY;
                    panelStartX = rect.left - containerRect.left;
                    panelStartY = rect.top - containerRect.top;
                    panelStartWidth = rect.width;
                    panelStartHeight = rect.height;
                    
                    e.preventDefault();
                    e.stopPropagation();
                });
                panel.appendChild(handle);
            });
        }
        
        function removeResizeHandles(panel) {
            const handles = panel.querySelectorAll('.resize-handle');
            handles.forEach(handle => handle.remove());
        }
        
        // グローバルマウスイベント
        document.addEventListener('mousemove', function(e) {
            if (draggingPanel && freeMode) {
                const containerRect = draggingPanel.parentElement.getBoundingClientRect();
                const diffX = e.clientX - dragStartX;
                const diffY = e.clientY - dragStartY;
                
                let newX = panelStartX + diffX;
                let newY = panelStartY + diffY;
                
                // コンテナ内に制限
                const panelRect = draggingPanel.getBoundingClientRect();
                newX = Math.max(0, Math.min(newX, containerRect.width - panelRect.width));
                newY = Math.max(0, Math.min(newY, containerRect.height - panelRect.height));
                
                draggingPanel.style.left = newX + 'px';
                draggingPanel.style.top = newY + 'px';
            }
            
            if (resizingPanel && freeMode && resizeDirection) {
                const containerRect = resizingPanel.parentElement.getBoundingClientRect();
                const diffX = e.clientX - dragStartX;
                const diffY = e.clientY - dragStartY;
                
                let newX = panelStartX;
                let newY = panelStartY;
                let newWidth = panelStartWidth;
                let newHeight = panelStartHeight;
                
                if (resizeDirection.includes('e')) {
                    newWidth = panelStartWidth + diffX;
                }
                if (resizeDirection.includes('w')) {
                    newWidth = panelStartWidth - diffX;
                    newX = panelStartX + diffX;
                }
                if (resizeDirection.includes('s')) {
                    newHeight = panelStartHeight + diffY;
                }
                if (resizeDirection.includes('n')) {
                    newHeight = panelStartHeight - diffY;
                    newY = panelStartY + diffY;
                }
                
                // 最小サイズ制限
                const minWidth = 200;
                const minHeight = 200;
                
                if (newWidth < minWidth) {
                    if (resizeDirection.includes('w')) {
                        newX = panelStartX + panelStartWidth - minWidth;
                    }
                    newWidth = minWidth;
                }
                if (newHeight < minHeight) {
                    if (resizeDirection.includes('n')) {
                        newY = panelStartY + panelStartHeight - minHeight;
                    }
                    newHeight = minHeight;
                }
                
                // コンテナ内に制限
                if (newX < 0) {
                    newWidth += newX;
                    newX = 0;
                }
                if (newY < 0) {
                    newHeight += newY;
                    newY = 0;
                }
                if (newX + newWidth > containerRect.width) {
                    newWidth = containerRect.width - newX;
                }
                if (newY + newHeight > containerRect.height) {
                    newHeight = containerRect.height - newY;
                }
                
                setPanelPosition(resizingPanel, newX, newY, newWidth, newHeight);
                
                // エディタとプレビューの高さを調整
                updatePanelContentHeight(resizingPanel);
            }
        });
        
        function updatePanelContentHeight(panel) {
            const headerHeight = panel.querySelector('.panel-header')?.offsetHeight || 60;
            const panelHeight = panel.offsetHeight;
            const contentHeight = panelHeight - headerHeight;
            
            if (panel.id === 'editorPanel') {
                const editorWrapper = panel.querySelector('.editor-wrapper');
                if (editorWrapper) {
                    editorWrapper.style.height = contentHeight + 'px';
                }
                const editor = panel.querySelector('.editor');
                if (editor) {
                    editor.style.height = contentHeight + 'px';
                }
            } else if (panel.id === 'previewPanel') {
                const preview = panel.querySelector('.preview');
                if (preview) {
                    preview.style.height = contentHeight + 'px';
                }
            }
        }
        
        // リサイズ時に高さを更新
        const resizeObserver = new ResizeObserver(function(entries) {
            if (!freeMode) return;
            entries.forEach(entry => {
                if (entry.target.classList.contains('editor-panel')) {
                    updatePanelContentHeight(entry.target);
                }
            });
        });
        
        // パネルのリサイズを監視
        document.addEventListener('DOMContentLoaded', function() {
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            if (editorPanel) resizeObserver.observe(editorPanel);
            if (previewPanel) resizeObserver.observe(previewPanel);
        });
        
        document.addEventListener('mouseup', function() {
            if (draggingPanel) {
                const panelId = draggingPanel.id;
                const rect = draggingPanel.getBoundingClientRect();
                const containerRect = draggingPanel.parentElement.getBoundingClientRect();
                
                savePanelPosition(panelId, 
                    rect.left - containerRect.left,
                    rect.top - containerRect.top,
                    rect.width,
                    rect.height
                );
                
                draggingPanel.querySelector('.panel-header').classList.remove('dragging');
                draggingPanel.classList.remove('dragging');
                draggingPanel = null;
            }
            
            if (resizingPanel) {
                const panelId = resizingPanel.id;
                const rect = resizingPanel.getBoundingClientRect();
                const containerRect = resizingPanel.parentElement.getBoundingClientRect();
                
                savePanelPosition(panelId,
                    rect.left - containerRect.left,
                    rect.top - containerRect.top,
                    rect.width,
                    rect.height
                );
                
                resizingPanel.classList.remove('resizing');
                resizingPanel.querySelectorAll('.resize-handle').forEach(h => h.classList.remove('resizing'));
                resizingPanel = null;
                resizeDirection = '';
            }
        });
        
        // グローバル関数として公開
        window.toggleFreeMode = toggleFreeMode;
        
        // 全画面表示の切り替え
        window.toggleFullscreen = function toggleFullscreen(panelId) {
            const panel = document.getElementById(panelId);
            if (!panel) return;
            
            const isFullscreen = panel.classList.contains('panel-fullscreen');
            const btn = panel.querySelector('.btn-fullscreen');
            
            if (isFullscreen) {
                // 全画面を解除
                panel.classList.remove('panel-fullscreen');
                if (btn) {
                    btn.textContent = '⛶';
                    btn.title = '全画面表示';
                }
                // 他のパネルを表示
                const otherPanel = panelId === 'editorPanel' ? document.getElementById('previewPanel') : document.getElementById('editorPanel');
                const editorContainer = document.querySelector('.editor-container');
                if (otherPanel && editorContainer) {
                    otherPanel.style.display = '';
                    editorContainer.style.display = 'flex';
                }
            } else {
                // 全画面表示
                panel.classList.add('panel-fullscreen');
                if (btn) {
                    btn.textContent = '⛶';
                    btn.title = '全画面解除';
                }
                // 他のパネルを非表示
                const otherPanel = panelId === 'editorPanel' ? document.getElementById('previewPanel') : document.getElementById('editorPanel');
                const editorContainer = document.querySelector('.editor-container');
                if (otherPanel && editorContainer) {
                    otherPanel.style.display = 'none';
                    editorContainer.style.display = 'block';
                }
                // エスケープキーで全画面解除
                const escapeHandler = function(e) {
                    if (e.key === 'Escape' && panel.classList.contains('panel-fullscreen')) {
                        toggleFullscreen(panelId);
                        document.removeEventListener('keydown', escapeHandler);
                    }
                };
                document.addEventListener('keydown', escapeHandler);
            }
        };
        
        // プレビューを更新
        function updatePreview() {
            const editor = getEditor();
            const preview = document.getElementById('preview');
            if (!editor || !preview) return;
            
            let content = editor.value;
            
            // CSSの読み込みを修正: rel="preload" を rel="stylesheet" に変換
            // より包括的なパターンマッチングで、様々な属性の組み合わせに対応
            content = content.replace(
                /<link\s+([^>]*)\s+rel=["']preload["']\s+([^>]*)\s+href=["']([^"']+)["']\s+([^>]*)\s+as=["']style["']\s*([^>]*)>/gi,
                function(match, before, middle2, href, middle2, after) {
                    // media属性がある場合は保持
                    const mediaMatch = (before + middle2 + middle2 + after).match(/media=["']([^"']+)["']/i);
                    const mediaAttr = mediaMatch ? ` media="${mediaMatch[2]}"` : '';
                    return `<link rel="stylesheet" href="${href}"${mediaAttr}>`;
                }
            );
            
            // より単純なパターンも処理（属性の順序が異なる場合）
            content = content.replace(
                /<link\s+rel=["']preload["']\s+href=["']([^"']+)["']\s+as=["']style["']\s*[^>]*>/gi,
                function(match, href) {
                    // media属性を抽出
                    const mediaMatch = match.match(/media=["']([^"']+)["']/i);
                    const mediaAttr = mediaMatch ? ` media="${mediaMatch[2]}"` : '';
                    return `<link rel="stylesheet" href="${href}"${mediaAttr}>`;
                }
            );
            
            // 相対パスのCSS/JS/画像を絶対URLに変換
            // Blob URLのコンテキストでは相対パスが解決されないため、絶対URLに変換する必要がある
            const currentFilename = window.editorFilename || '';
            let baseUrl = window.location.origin;
            let basePath = '';
            
            // ファイル名からベースパスを推測（相対パスの解決に使用）
            if (currentFilename) {
                // ファイル名からディレクトリパスを取得
                const filePath = currentFilename.split('/');
                filePath.pop(); // ファイル名を削除
                const dirPath = filePath.join('/');
                if (dirPath) {
                    basePath = '/' + dirPath;
                    if (!basePath.endsWith('/')) {
                        basePath += '/';
                    }
                    baseUrl = window.location.origin + basePath;
                } else {
                    basePath = '/';
                }
            } else {
                basePath = '/';
            }
            
            // 相対パスを絶対URLに変換するヘルパー関数
            function resolvePath(path) {
                // 絶対URLやdata URIの場合はそのまま
                if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//') || path.startsWith('data:')) {
                    return path;
                }
                
                // 相対パスを絶対URLに変換
                if (path.startsWith('../')) {
                    // ../ で始まる場合は、ベースパスから相対的に解決
                    const pathParts = basePath.split('/').filter(p => p);
                    const relativeParts = path.split('/').filter(p => p);
                    
                    for (const part of relativeParts) {
                        if (part === '..') {
                            if (pathParts.length > 1) {
                                pathParts.pop();
                            }
                        } else if (part !== '.') {
                            pathParts.push(part);
                        }
                    }
                    
                    return window.location.origin + '/' + pathParts.join('/');
                } else if (path.startsWith('./')) {
                    return window.location.origin + basePath + path.substring(3);
                } else if (path.startsWith('/')) {
                    return window.location.origin + path;
                } else {
                    return window.location.origin + basePath + path;
                }
            }
            
            // href属性の相対パスを変換（linkタグ）
            content = content.replace(
                /(<link[^>]*href=["'])([^"']+)(["'][^>]*>)/gi,
                function(match, prefix, path, suffix) {
                    const resolvedPath = resolvePath(path);
                    return prefix + resolvedPath + suffix;
                }
            );
            
            // src属性の相対パスを変換（img, script, iframeタグ）
            content = content.replace(
                /(<(?:img|script|iframe)[^>]*src=["'])([^"']+)(["'][^>]*>)/gi,
                function(match, prefix, path, suffix) {
                    const resolvedPath = resolvePath(path);
                    return prefix + resolvedPath + suffix;
                }
            );
            
            // CSSの@import内の相対パスも変換
            content = content.replace(
                /(@import\s+(?:url\()?["'])([^"']+)(["']\)?;)/gi,
                function(match, prefix, path, suffix) {
                    const resolvedPath = resolvePath(path);
                    return prefix + resolvedPath + suffix;
                }
            );
            
            // プレビュー内のコンテンツの視認性を向上させるため、基本スタイルを追加
            // bodyタグにスタイルが指定されていない場合、デフォルトスタイルを追加
            if (!content.match(/<body[^>]*style/i) && !content.match(/<style/i)) {
                const styleTag = '<style>body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #2d3748; background: #ffffff; padding: 20px; }</style>';
                if (content.includes('</head>')) {
                    content = content.replace('</head>', styleTag + '</head>');
                } else if (content.includes('<body')) {
                    content = content.replace('<body', styleTag + '<body');
                } else {
                    content = styleTag + content;
                }
            }
            
            const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            
            // 以前のBlob URLを解放（メモリリークを防ぐ）
            if (preview.dataset.blobUrl) {
                URL.revokeObjectURL(preview.dataset.blobUrl);
            }
            preview.dataset.blobUrl = url;
            
            preview.src = url;
            
            // プレビューが読み込まれた際の視認性向上のための処理
            preview.onload = function() {
                try {
                    const previewDoc = preview.contentDocument || preview.contentWindow.document;
                    if (previewDoc && previewDoc.body) {
                        // プレビュー内のテキストの視認性を向上
                        const body = previewDoc.body;
                        if (!body.style.color) {
                            body.style.color = '#2d3748';
                        }
                        if (!body.style.backgroundColor) {
                            body.style.backgroundColor = '#ffffff';
                        }
                        if (!body.style.fontFamily) {
                            body.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
                        }
                        if (!body.style.lineHeight) {
                            body.style.lineHeight = '1.6';
                        }
                        
                        // ハイライトスタイルとラベル視認性向上スタイルを追加
                        const style = previewDoc.createElement('style');
                        style.textContent = `
                            .preview-highlight {
                                outline: 3px solid #667eea !important;
                                outline-offset: 2px !important;
                                background-color: rgba(102, 126, 234, 0.1) !important;
                                transition: all 0.2s ease !important;
                                box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.3) !important;
                                border-radius: 2px !important;
                            }
                            .preview-highlight-label {
                                outline: 3px solid #48bb78 !important;
                                outline-offset: 2px !important;
                                background-color: rgba(72, 187, 120, 0.15) !important;
                                transition: all 0.2s ease !important;
                                box-shadow: 0 0 0 2px rgba(72, 187, 120, 0.4) !important;
                                border-radius: 2px !important;
                            }
                            /* ラベル要素の視認性向上 */
                            label {
                                display: inline-block !important;
                                padding: 8px 12px !important;
                                margin: 4px 2px !important;
                                background: linear-gradient(135deg, #e6fffa 0%, #b2f5ea 100%) !important;
                                border: 2px solid #38a169 !important;
                                border-radius: 6px !important;
                                color: #22543d !important;
                                font-weight: 600 !important;
                                font-size: 14px !important;
                                line-height: 1.5 !important;
                                box-shadow: 0 2px 4px rgba(56, 161, 105, 0.2) !important;
                                transition: all 0.2s ease !important;
                                cursor: pointer !important;
                                min-height: 36px !important;
                                vertical-align: middle !important;
                            }
                            label:hover {
                                background: linear-gradient(135deg, #b2f5ea 0%, #81e6d9 100%) !important;
                                border-color: #2f855a !important;
                                box-shadow: 0 4px 8px rgba(56, 161, 105, 0.3) !important;
                                transform: translateY(-1px) !important;
                            }
                            label:focus-within {
                                background: linear-gradient(135deg, #81e6d9 0%, #4fd1c7 100%) !important;
                                border-color: #2c7a7b !important;
                                box-shadow: 0 0 0 3px rgba(56, 161, 105, 0.2) !important;
                            }
                            /* ラベル内のinput要素のスタイル */
                            label input[type="radio"],
                            label input[type="checkbox"] {
                                margin-right: 6px !important;
                                margin-left: 0 !important;
                                width: 18px !important;
                                height: 18px !important;
                                cursor: pointer !important;
                                accent-color: #38a169 !important;
                            }
                            label input[type="text"],
                            label input[type="email"],
                            label input[type="password"],
                            label input[type="number"],
                            label select,
                            label textarea {
                                margin-left: 8px !important;
                                padding: 6px 10px !important;
                                border: 1px solid #cbd5e0 !important;
                                border-radius: 4px !important;
                                font-size: 14px !important;
                            }
                            /* ラベルと関連要素の視覚的接続 */
                            label + input:not([type="radio"]):not([type="checkbox"]),
                            label + select,
                            label + textarea {
                                margin-top: 4px !important;
                                border-left: 3px solid #38a169 !important;
                            }
                            /* for属性で接続された要素のスタイル */
                            input[id]:focus,
                            select[id]:focus,
                            textarea[id]:focus {
                                border-left: 3px solid #38a169 !important;
                                box-shadow: 0 0 0 2px rgba(56, 161, 105, 0.2) !important;
                            }
                            /* 要素識別バッジ（比較用） */
                            .element-badge {
                                display: inline-block !important;
                                position: absolute !important;
                                top: -8px !important;
                                left: -8px !important;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                                color: white !important;
                                font-size: 10px !important;
                                font-weight: 700 !important;
                                padding: 2px 6px !important;
                                border-radius: 4px !important;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
                                z-index: 1000 !important;
                                pointer-events: none !important;
                                white-space: nowrap !important;
                                max-width: 200px !important;
                                overflow: hidden !important;
                                text-overflow: ellipsis !important;
                            }
                            .element-badge.tag {
                                background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%) !important;
                            }
                            .element-badge.id {
                                background: linear-gradient(135deg, #48bb78 0%, #38a169 100%) !important;
                            }
                            .element-badge.class {
                                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
                            }
                            /* 要素に相対位置を設定 */
                            label, input, select, textarea, button, div, span, p, h1, h2, h3, h4, h5, h6 {
                                position: relative !important;
                            }
                            /* ツールチップスタイル */
                            .element-tooltip {
                                position: absolute !important;
                                bottom: 100% !important;
                                left: 0 !important;
                                margin-bottom: 5px !important;
                                background: rgba(0, 0, 0, 0.9) !important;
                                color: white !important;
                                padding: 6px 10px !important;
                                border-radius: 4px !important;
                                font-size: 11px !important;
                                white-space: nowrap !important;
                                z-index: 10000 !important;
                                pointer-events: none !important;
                                opacity: 0 !important;
                                transition: opacity 0.2s ease !important;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
                            }
                            .element-tooltip::after {
                                content: '' !important;
                                position: absolute !important;
                                top: 100% !important;
                                left: 10px !important;
                                border: 5px solid transparent !important;
                                border-top-color: rgba(0, 0, 0, 0.9) !important;
                            }
                            label:hover .element-tooltip,
                            input:hover .element-tooltip,
                            select:hover .element-tooltip,
                            textarea:hover .element-tooltip,
                            button:hover .element-tooltip {
                                opacity: 1 !important;
                            }
                        `;
                        if (!previewDoc.head.querySelector('style[data-preview-highlight]')) {
                            style.setAttribute('data-preview-highlight', 'true');
                            previewDoc.head.appendChild(style);
                        }
                        
                        // プレビュー内の要素に識別情報を追加（比較用）
                        addElementIdentifiers(previewDoc);
                        
                        // プレビュー更新後にハイライトを再適用
                        setTimeout(function() {
                            highlightPreviewElement();
                        }, 100);
                    }
                } catch (e) {
                    // クロスオリジン制限などでアクセスできない場合は無視
                    console.log('Preview styling: ' + e.message);
                }
            };
        }
        
        // プレビュー内の要素に識別情報を追加（比較用）
        function addElementIdentifiers(previewDoc) {
            if (!previewDoc || !previewDoc.body) return;
            
            // 識別対象の要素を取得（主要なフォーム要素と構造要素）
            const elementsToIdentify = previewDoc.querySelectorAll('label, input, select, textarea, button, div[id], div[class], span[id], span[class], p[id], p[class], h1, h2, h3, h4, h5, h6');
            
            elementsToIdentify.forEach(function(element) {
                // 既に識別情報が追加されている場合はスキップ
                if (element.dataset.identifierAdded === 'true') return;
                
                const tagName = element.tagName.toLowerCase();
                const id = element.id || '';
                const className = element.className || '';
                const classes = className ? className.split(/\s+/).filter(c => c && c !== 'element-badge' && c !== 'element-tooltip').slice(0, 3) : [];
                
                // 識別情報を収集
                const identifiers = [];
                
                // タグ名
                identifiers.push({ type: 'tag', value: tagName, label: tagName.toUpperCase() });
                
                // ID
                if (id) {
                    identifiers.push({ type: 'id', value: id, label: '#' + id });
                }
                
                // クラス（最大3つまで）
                if (classes.length > 0) {
                    classes.forEach(cls => {
                        identifiers.push({ type: 'class', value: cls, label: '.' + cls });
                    });
                }
                
                // 識別情報がある場合のみバッジを追加
                if (identifiers.length > 0) {
                    // 最初の識別情報をバッジとして表示
                    const primaryIdentifier = identifiers[0];
                    const badge = previewDoc.createElement('span');
                    badge.className = 'element-badge ' + primaryIdentifier.type;
                    badge.textContent = primaryIdentifier.label;
                    badge.title = identifiers.map(i => i.label).join(' ');
                    element.appendChild(badge);
                    
                    // すべての識別情報をツールチップとして表示
                    if (identifiers.length > 1) {
                        const tooltip = previewDoc.createElement('div');
                        tooltip.className = 'element-tooltip';
                        tooltip.textContent = identifiers.map(i => i.label).join(' ');
                        element.appendChild(tooltip);
                    }
                    
                    element.dataset.identifierAdded = 'true';
                }
            });
        }
        
        // プレビュー内の要素をハイライト
        function highlightPreviewElement() {
            const editor = getEditor();
            const preview = document.getElementById('preview');
            if (!editor || !preview) return;
            
            try {
                const previewDoc = preview.contentDocument || preview.contentWindow.document;
                if (!previewDoc || !previewDoc.body) return;
                
                // 以前のハイライトを削除
                const previousHighlights = previewDoc.querySelectorAll('.preview-highlight, .preview-highlight-label');
                previousHighlights.forEach(el => {
                    el.classList.remove('preview-highlight', 'preview-highlight-label');
                });
                
                // エディタのカーソル位置を取得
                const cursorPos = editor.selectionStart;
                const content = editor.value;
                
                if (cursorPos < 0 || cursorPos > content.length) return;
                
                // カーソル位置周辺のHTMLタグを特定
                let tagStart = -1;
                let tagEnd = -1;
                let tagName = '';
                let isLabel = false;
                
                // カーソル位置から後方に検索（開始タグ）
                for (let i = cursorPos; i >= 0; i--) {
                    if (content[i] === '<' && i < content.length - 1) {
                        // タグ名を抽出
                        let j = i + 1;
                        let tag = '';
                        while (j < content.length && /[a-zA-Z0-9]/.test(content[j])) {
                            tag += content[j];
                            j++;
                        }
                        if (tag && !tag.startsWith('/') && !tag.startsWith('!')) {
                            tagName = tag.toLowerCase();
                            tagStart = i;
                            tagEnd = content.indexOf('>', i);
                            if (tagEnd === -1) break;
                            tagEnd++;
                            
                            // labelタグかどうかを確認
                            if (tagName === 'label') {
                                isLabel = true;
                            }
                            break;
                        }
                    }
                }
                
                if (tagStart === -1 || !tagName) return;
                
                // プレビュー内で対応する要素を検索
                // ID、クラス、またはタグ名で要素を特定
                const tagContent = content.substring(tagStart, tagEnd);
                
                // ID属性を抽出
                const idMatch = tagContent.match(/id=["']([^"']+)["']/i);
                const classMatch = tagContent.match(/class=["']([^"']+)["']/i);
                const forMatch = tagContent.match(/for=["']([^"']+)["']/i);
                
                let targetElement = null;
                
                // IDで検索（最優先）
                if (idMatch) {
                    targetElement = previewDoc.getElementById(idMatch[1]);
                }
                
                // for属性で検索（labelタグの場合）
                if (!targetElement && isLabel && forMatch) {
                    targetElement = previewDoc.querySelector(`label[for="${forMatch[1]}"]`);
                    if (!targetElement) {
                        const targetInput = previewDoc.getElementById(forMatch[1]);
                        if (targetInput) {
                            targetElement = targetInput;
                        }
                    }
                }
                
                // クラスで検索
                if (!targetElement && classMatch) {
                    const classes = classMatch[1].split(/\s+/);
                    const selector = '.' + classes.join('.');
                    const elements = previewDoc.querySelectorAll(selector);
                    if (elements.length > 0) {
                        // カーソル位置に最も近い要素を選択
                        targetElement = elements[0];
                    }
                }
                
                // タグ名で検索（最後の手段）
                if (!targetElement) {
                    const elements = previewDoc.querySelectorAll(tagName);
                    if (elements.length > 0) {
                        targetElement = elements[0];
                    }
                }
                
                // ハイライトを適用
                if (targetElement) {
                    if (isLabel || tagName === 'label') {
                        targetElement.classList.add('preview-highlight-label');
                    } else {
                        targetElement.classList.add('preview-highlight');
                    }
                    
                    // 要素が見えるようにスクロール
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center',
                        inline: 'nearest'
                    });
                }
            } catch (e) {
                // クロスオリジン制限などでアクセスできない場合は無視
                console.log('Preview highlight: ' + e.message);
            }
        }
        
        // リモコン盤の初期化
        function initRemoteControl() {
            const remoteControl = document.getElementById('remoteControl');
            const remoteControlHeader = document.getElementById('remoteControlHeader');
            if (!remoteControl || !remoteControlHeader) return;
            
            // 保存された位置と状態を復元
            const savedPosition = localStorage.getItem('remoteControlPosition');
            const savedState = localStorage.getItem('remoteControlState');
            
            if (savedPosition) {
                const pos = JSON.parse(savedPosition);
                remoteControl.style.left = pos.x + 'px';
                remoteControl.style.top = pos.y + 'px';
            } else {
                // デフォルト位置（右上）
                remoteControl.style.right = '20px';
                remoteControl.style.top = '20px';
            }
            
            if (savedState === 'collapsed') {
                remoteControl.classList.add('collapsed');
                const toggleBtn = document.getElementById('remoteControlToggle');
                if (toggleBtn) toggleBtn.textContent = '▲';
            }
            
            // ドラッグ機能
            let isDragging = false;
            let dragStartX = 0;
            let dragStartY = 0;
            let startLeft = 0;
            let startTop = 0;
            
            remoteControlHeader.addEventListener('mousedown', function(e) {
                // 開閉ボタンをクリックした場合はドラッグしない
                if (e.target.closest('.remote-control-toggle')) return;
                
                isDragging = true;
                remoteControl.classList.add('dragging');
                
                const rect = remoteControl.getBoundingClientRect();
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                startLeft = rect.left;
                startTop = rect.top;
                
                e.preventDefault();
            });
            
            document.addEventListener('mousemove', function(e) {
                if (!isDragging) return;
                
                const diffX = e.clientX - dragStartX;
                const diffY = e.clientY - dragStartY;
                
                let newLeft = startLeft + diffX;
                let newTop = startTop + diffY;
                
                // 画面外に出ないように制限
                const maxLeft = window.innerWidth - remoteControl.offsetWidth;
                const maxTop = window.innerHeight - remoteControl.offsetHeight;
                
                newLeft = Math.max(0, Math.min(newLeft, maxLeft));
                newTop = Math.max(0, Math.min(newTop, maxTop));
                
                remoteControl.style.left = newLeft + 'px';
                remoteControl.style.top = newTop + 'px';
                remoteControl.style.right = 'auto';
                remoteControl.style.bottom = 'auto';
                
                // 位置を保存
                localStorage.setItem('remoteControlPosition', JSON.stringify({
                    x: newLeft,
                    y: newTop
                }));
            });
            
            document.addEventListener('mouseup', function() {
                if (isDragging) {
                    isDragging = false;
                    remoteControl.classList.remove('dragging');
                }
            });
        }
        
        // リモコン盤の開閉
        window.toggleRemoteControl = function() {
            const remoteControl = document.getElementById('remoteControl');
            const toggleBtn = document.getElementById('remoteControlToggle');
            if (!remoteControl || !toggleBtn) return;
            
            remoteControl.classList.toggle('collapsed');
            const isCollapsed = remoteControl.classList.contains('collapsed');
            toggleBtn.textContent = isCollapsed ? '▲' : '▼';
            
            // 状態を保存
            localStorage.setItem('remoteControlState', isCollapsed ? 'collapsed' : 'expanded');
        };
        
        // 利用手順パネルの初期化
        function initUsageGuide() {
            const usageGuide = document.getElementById('usageGuide');
            const usageGuideHeader = document.getElementById('usageGuideHeader');
            if (!usageGuide || !usageGuideHeader) return;
            
            // 保存された位置と状態を復元
            const savedPosition = localStorage.getItem('usageGuidePosition');
            const savedState = localStorage.getItem('usageGuideState');
            
            if (savedPosition) {
                const pos = JSON.parse(savedPosition);
                usageGuide.style.left = pos.x + 'px';
                usageGuide.style.top = pos.y + 'px';
            } else {
                // デフォルト位置（左下）
                usageGuide.style.left = '20px';
                usageGuide.style.bottom = '20px';
            }
            
            if (savedState === 'collapsed') {
                usageGuide.classList.add('collapsed');
                const toggleBtn = document.getElementById('usageGuideToggle');
                if (toggleBtn) toggleBtn.textContent = '▲';
            }
            
            // ドラッグ機能
            let isDragging = false;
            let dragStartX = 0;
            let dragStartY = 0;
            let startLeft = 0;
            let startTop = 0;
            
            usageGuideHeader.addEventListener('mousedown', function(e) {
                // 開閉ボタンをクリックした場合はドラッグしない
                if (e.target.closest('.usage-guide-toggle')) return;
                
                isDragging = true;
                usageGuide.classList.add('dragging');
                
                const rect = usageGuide.getBoundingClientRect();
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                startLeft = rect.left;
                startTop = rect.top;
                
                e.preventDefault();
            });
            
            document.addEventListener('mousemove', function(e) {
                if (!isDragging) return;
                
                const diffX = e.clientX - dragStartX;
                const diffY = e.clientY - dragStartY;
                
                let newLeft = startLeft + diffX;
                let newTop = startTop + diffY;
                
                // 画面外に出ないように制限
                const maxLeft = window.innerWidth - usageGuide.offsetWidth;
                const maxTop = window.innerHeight - usageGuide.offsetHeight;
                
                newLeft = Math.max(0, Math.min(newLeft, maxLeft));
                newTop = Math.max(0, Math.min(newTop, maxTop));
                
                usageGuide.style.left = newLeft + 'px';
                usageGuide.style.top = newTop + 'px';
                usageGuide.style.bottom = 'auto';
                usageGuide.style.right = 'auto';
                
                // 位置を保存
                localStorage.setItem('usageGuidePosition', JSON.stringify({
                    x: newLeft,
                    y: newTop
                }));
            });
            
            document.addEventListener('mouseup', function() {
                if (isDragging) {
                    isDragging = false;
                    usageGuide.classList.remove('dragging');
                }
            });
        }
        
        // 利用手順パネルの開閉
        window.toggleUsageGuide = function() {
            const usageGuide = document.getElementById('usageGuide');
            const toggleBtn = document.getElementById('usageGuideToggle');
            if (!usageGuide || !toggleBtn) return;
            
            usageGuide.classList.toggle('collapsed');
            const isCollapsed = usageGuide.classList.contains('collapsed');
            toggleBtn.textContent = isCollapsed ? '▲' : '▼';
            
            // 状態を保存
            localStorage.setItem('usageGuideState', isCollapsed ? 'collapsed' : 'expanded');
        };
        
        // イベントリスナーを設定
        function setupToggleButtons() {
            const usageGuideToggle = document.getElementById('usageGuideToggle');
            if (usageGuideToggle) {
                usageGuideToggle.addEventListener('click', toggleUsageGuide);
            }
            
            const remoteControlToggle = document.getElementById('remoteControlToggle');
            if (remoteControlToggle) {
                remoteControlToggle.addEventListener('click', toggleRemoteControl);
            }
            
            const uploadBtnMain = document.getElementById('uploadBtnMain');
            if (uploadBtnMain) {
                uploadBtnMain.addEventListener('click', showUploadModal);
            }
        }
        
        // テンプレート統合の状態保存イベントリスナーを設定
        function setupTemplateMergeStateSaving() {
            // ファイル選択チェックボックスの変更を監視
            document.addEventListener('change', function(e) {
                if (e.target.classList.contains('template-file-checkbox')) {
                    saveTemplateMergeState();
                }
            });
            
            // オプションの変更を監視
            const optionIds = ['mergeOptionStructure', 'mergeOptionStyles', 'mergeOptionContent', 'mergeOptionAttributes', 'mergeDiffHandling'];
            optionIds.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.addEventListener('change', saveTemplateMergeState);
                }
            });
            
            // ディレクトリパスの変更を監視
            const dirInput = document.getElementById('templateMergeDir');
            const dirSelect = document.getElementById('templateMergeDirSelect');
            if (dirInput) {
                dirInput.addEventListener('change', saveTemplateMergeState);
                dirInput.addEventListener('blur', saveTemplateMergeState);
            }
            if (dirSelect) {
                dirSelect.addEventListener('change', saveTemplateMergeState);
            }
        }
        
        // 画面比較の状態を保存
        function saveScreenComparisonState() {
            const state = {
                dirPath: document.getElementById('comparisonDir')?.value || '',
                quickDirPath: document.getElementById('quickComparisonDir')?.value || '',
                files: comparisonFiles.map(file => ({
                    name: file.name,
                    path: file.path,
                    type: file.type,
                    size: file.size
                })),
                selectedFiles: Array.from(document.querySelectorAll('.comparison-file-checkbox:checked')).map(cb => cb.value),
                gridMode: document.getElementById('comparisonGridMode')?.value || 'auto',
                layout: document.getElementById('comparisonLayout')?.value || 'grid',
                comparisonMode: comparisonMode
            };
            localStorage.setItem('screenComparisonState', JSON.stringify(state));
        }
        
        // 画面比較の状態を復元
        function restoreScreenComparisonState() {
            try {
                const saved = localStorage.getItem('screenComparisonState');
                if (!saved) return false;
                
                const state = JSON.parse(saved);
                
                // ディレクトリパスを復元
                const comparisonDir = document.getElementById('comparisonDir');
                const quickComparisonDir = document.getElementById('quickComparisonDir');
                if (comparisonDir && state.dirPath) {
                    comparisonDir.value = state.dirPath;
                }
                if (quickComparisonDir && state.quickDirPath) {
                    quickComparisonDir.value = state.quickDirPath;
                }
                
                // ファイルリストを復元
                if (state.files && state.files.length > 0) {
                    comparisonFiles = state.files;
                    displayComparisonFiles();
                    updateQuickFileCount();
                    
                    // 選択状態を復元
                    if (state.selectedFiles && state.selectedFiles.length > 0) {
                        setTimeout(() => {
                            state.selectedFiles.forEach(filePath => {
                                const checkbox = document.querySelector(`.comparison-file-checkbox[value="${filePath}"]`);
                                if (checkbox) {
                                    checkbox.checked = true;
                                }
                            });
                        }, 300);
                    }
                }
                
                // グリッドモードを復元
                if (state.gridMode) {
                    const gridModeSelect = document.getElementById('comparisonGridMode');
                    if (gridModeSelect) {
                        gridModeSelect.value = state.gridMode;
                    }
                }
                
                // レイアウトを復元
                if (state.layout) {
                    const layoutSelect = document.getElementById('comparisonLayout');
                    if (layoutSelect) {
                        layoutSelect.value = state.layout;
                        updateComparisonLayout();
                    }
                }
                
                // 比較モードを復元
                if (state.comparisonMode !== undefined) {
                    comparisonMode = state.comparisonMode;
                }
                
                return true;
            } catch (error) {
                console.error('画面比較の状態復元エラー:', error);
                return false;
            }
        }
        
        // ボタンの表示を確認・強制表示（リモコン盤内のボタン用）
        function ensureButtonsVisible() {
            const uploadBtn = document.getElementById('uploadBtnMain');
            const downloadBtn = document.getElementById('downloadBtn');
            
            if (uploadBtn) {
                uploadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 1 !important; font-weight: 600; background: #667eea; border: 2px solid #5568d3; color: white;';
            }
            
            if (downloadBtn) {
                if (downloadBtn.disabled) {
                    downloadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 0.5 !important;';
                } else {
                    downloadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 1 !important; font-weight: 600; background: #48bb78; border-color: #38a169; color: white;';
                }
            }
        }
        
        // ページ読み込み時に実行
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', ensureButtonsVisible);
        } else {
            ensureButtonsVisible();
        }
        
        window.addEventListener('load', function() {
            ensureButtonsVisible();
            setTimeout(ensureButtonsVisible, 100);
            setTimeout(ensureButtonsVisible, 500);
            setTimeout(ensureButtonsVisible, 1000);
        });
        
        // ファイルを保存（グローバル関数として明示的に定義）
        window.saveFile = async function saveFile() {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            const content = editor.value;
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ content: content })
                });
                
                const data = await response.json();
                if (data.success) {
                    showStatus('ファイルを保存しました！', 'success');
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // ファイルを再読み込み（グローバル関数として明示的に定義）
        window.reloadFile = async function reloadFile() {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            try {
                const response = await fetch('/reload');
                const data = await response.json();
                if (data.success) {
                    editor.value = data.content;
                    updatePreview();
                    showStatus('ファイルを再読み込みしました！', 'success');
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // HTMLソースをクリア（グローバル関数として明示的に定義）
        window.clearEditor = function clearEditor() {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            
            // 確認ダイアログを表示
            if (!confirm('HTMLソースをクリアしますか？この操作は取り消せません。')) {
                return;
            }
            
            // エディタの内容をクリア
            editor.value = '';
            updatePreview();
            showStatus('HTMLソースをクリアしました', 'success');
        };
        
        // 構造情報を表示
        window.showStructure = async function showStructure() {
            try {
                const response = await fetch('/structure');
                const data = await response.json();
                if (data.success) {
                    const info = data.info;
                    let html = '<div style="line-height: 1.8;">';
                    html += `<p><strong>タイトル:</strong> ${info.title || '(なし)'}</p>`;
                    html += `<p><strong>リンク数:</strong> ${info.links_count}</p>`;
                    html += `<p><strong>画像数:</strong> ${info.images_count}</p>`;
                    html += `<p><strong>スクリプト数:</strong> ${info.scripts_count}</p>`;
                    html += `<p><strong>スタイルシート数:</strong> ${info.stylesheets_count}</p>`;
                    html += `<p><strong>フォーム数:</strong> ${info.forms_count}</p>`;
                    if (Object.keys(info.meta_tags).length > 0) {
                        html += '<p><strong>メタタグ:</strong></p><ul style="margin-left: 20px;">';
                        for (const [name, content] of Object.entries(info.meta_tags)) {
                            html += `<li>${name}: ${content.substring(0, 50)}${content.length > 50 ? '...' : ''}</li>`;
                        }
                        html += '</ul>';
                    }
                    html += '</div>';
                    document.getElementById('structureInfo').innerHTML = html;
                    document.getElementById('structureModal').style.display = 'block';
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        }
        
        // 検索結果を保存するグローバル変数
        window.searchMatches = [];
        window.currentMatchIndex = -1;
        
        // HTMLソース内で検索文字列をハイライト表示
        function highlightInSource(query) {
            const editor = getEditor();
            if (!editor) return [];
            
            const content = editor.value;
            if (!content || !query) return [];
            
            // 検索文字列をエスケープ（正規表現の特殊文字を処理）
            const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedQuery, 'gi');
            const matches = [];
            let match;
            
            while ((match = regex.exec(content)) !== null) {
                matches.push({
                    start: match.index,
                    end: match.index + match[0].length,
                    text: match[0]
                });
            }
            
            return matches;
        }
        
        // すべての検索結果をハイライト表示
        function highlightAllMatches(matches) {
            const editor = getEditor();
            const highlightDiv = document.getElementById('editorHighlight');
            if (!editor || !highlightDiv) return;
            
            // ハイライトをクリア
            highlightDiv.innerHTML = '';
            
            if (matches.length === 0) return;
            
            const content = editor.value;
            
            // textareaの実際のスタイルを取得
            const editorStyle = window.getComputedStyle(editor);
            const lineHeight = parseFloat(editorStyle.lineHeight) || parseFloat(editorStyle.fontSize) * 1.6;
            const paddingTop = parseFloat(editorStyle.paddingTop) || 15;
            const paddingLeft = parseFloat(editorStyle.paddingLeft) || 15;
            const fontSize = parseFloat(editorStyle.fontSize) || 14;
            const fontFamily = editorStyle.fontFamily;
            
            // ハイライトdivのスタイルをtextareaと完全に一致させる
            highlightDiv.style.fontSize = editorStyle.fontSize;
            highlightDiv.style.fontFamily = editorStyle.fontFamily;
            highlightDiv.style.lineHeight = editorStyle.lineHeight;
            highlightDiv.style.padding = editorStyle.padding;
            highlightDiv.style.paddingTop = editorStyle.paddingTop;
            highlightDiv.style.paddingLeft = editorStyle.paddingLeft;
            highlightDiv.style.paddingRight = editorStyle.paddingRight;
            highlightDiv.style.paddingBottom = editorStyle.paddingBottom;
            
            // 各行の開始位置を計算
            const lines = content.split('\n');
            const lineStarts = [];
            let pos = 0;
            for (let i = 0; i < lines.length; i++) {
                lineStarts.push(pos);
                pos += lines[i].length + 1; // +1 for newline
            }
            
            // テキストの幅を計算するためのcanvas
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            context.font = fontSize + 'px ' + fontFamily;
            
            // 各マッチをハイライト
            matches.forEach(match => {
                // マッチが含まれる行を特定
                let lineIndex = 0;
                for (let i = 0; i < lineStarts.length; i++) {
                    if (match.start >= lineStarts[i]) {
                        lineIndex = i;
                    } else {
                        break;
                    }
                }
                
                // 行内での位置を計算
                const lineStart = lineStarts[lineIndex];
                const lineText = lines[lineIndex];
                const matchInLineStart = match.start - lineStart;
                const matchInLineEnd = Math.min(match.end - lineStart, lineText.length);
                
                // テキストの幅を計算
                const textBeforeMatch = lineText.substring(0, matchInLineStart);
                const matchText = lineText.substring(matchInLineStart, matchInLineEnd);
                const textWidth = context.measureText(textBeforeMatch).width;
                const matchWidth = context.measureText(matchText).width;
                
                // ハイライトマークを作成
                const mark = document.createElement('span');
                mark.className = 'highlight-mark';
                mark.style.top = (lineIndex * lineHeight + paddingTop) + 'px';
                mark.style.left = (textWidth + paddingLeft) + 'px';
                mark.style.width = matchWidth + 'px';
                mark.style.height = lineHeight + 'px';
                highlightDiv.appendChild(mark);
            });
            
            // textareaのスクロールに合わせてハイライトもスクロール
            // グローバルに保存して、他の場所からもアクセス可能にする
            if (!window.syncHighlightScroll) {
                window.syncHighlightScroll = function() {
                    const ed = getEditor();
                    const hd = document.getElementById('editorHighlight');
                    if (hd && ed) {
                        // requestAnimationFrameを使用してスムーズに同期
                        requestAnimationFrame(function() {
                            hd.scrollTop = ed.scrollTop;
                            hd.scrollLeft = ed.scrollLeft;
                        });
                    }
                };
            }
            
            // 既存のイベントリスナーを削除してから追加
            if (window.syncHighlightScrollHandler) {
                editor.removeEventListener('scroll', window.syncHighlightScrollHandler);
            }
            window.syncHighlightScrollHandler = window.syncHighlightScroll;
            editor.addEventListener('scroll', window.syncHighlightScrollHandler, { passive: true });
            
            // 初期同期
            requestAnimationFrame(function() {
                highlightDiv.scrollTop = editor.scrollTop;
                highlightDiv.scrollLeft = editor.scrollLeft;
            });
        }
        
        // 指定された位置をハイライト表示
        function highlightAtPosition(start, end) {
            const editor = getEditor();
            if (!editor) return;
            
            // textareaで選択範囲を設定
            editor.focus();
            editor.setSelectionRange(start, end);
            
            // 該当箇所にスクロール
            const lineHeight = 20; // おおよその行の高さ
            const linesBefore = editor.value.substring(0, start).split('\n').length - 1;
            const scrollTop = linesBefore * lineHeight;
            editor.scrollTop = Math.max(0, scrollTop - 100); // 少し上に余白を持たせる
        }
        
        // 次の検索結果へ移動
        window.highlightNext = function highlightNext() {
            if (window.searchMatches.length === 0) return;
            
            window.currentMatchIndex = (window.currentMatchIndex + 1) % window.searchMatches.length;
            const match = window.searchMatches[window.currentMatchIndex];
            highlightAtPosition(match.start, match.end);
            updateMatchCounter();
        };
        
        // 前の検索結果へ移動
        window.highlightPrevious = function highlightPrevious() {
            if (window.searchMatches.length === 0) return;
            
            window.currentMatchIndex = (window.currentMatchIndex - 1 + window.searchMatches.length) % window.searchMatches.length;
            const match = window.searchMatches[window.currentMatchIndex];
            highlightAtPosition(match.start, match.end);
            updateMatchCounter();
        };
        
        // 検索結果カウンターを更新
        function updateMatchCounter() {
            const counter = document.getElementById('matchCounter');
            if (window.searchMatches.length > 0) {
                counter.textContent = `${window.currentMatchIndex + 1} / ${window.searchMatches.length}`;
                counter.style.display = 'inline';
            } else {
                counter.style.display = 'none';
            }
        }
        
        // 要素を検索（グローバル関数として明示的に定義）
        window.searchElement = async function searchElement() {
            const editor = getEditor();
            if (!editor) {
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            
            const query = document.getElementById('searchBox').value.trim();
            if (!query) {
                showStatus('検索文字列を入力してください', 'error');
                return;
            }
            
            // HTMLソース内で検索文字列をハイライト
            window.searchMatches = highlightInSource(query);
            window.currentMatchIndex = -1;
            
            // すべての検索結果をハイライト表示
            highlightAllMatches(window.searchMatches);
            
            // 検索結果ボタンの表示/非表示
            const nextBtn = document.getElementById('nextMatchBtn');
            const prevBtn = document.getElementById('prevMatchBtn');
            if (window.searchMatches.length > 0) {
                nextBtn.style.display = 'inline-block';
                prevBtn.style.display = 'inline-block';
                // 最初の結果を選択
                window.currentMatchIndex = 0;
                highlightAtPosition(window.searchMatches[0].start, window.searchMatches[0].end);
                updateMatchCounter();
            } else {
                nextBtn.style.display = 'none';
                prevBtn.style.display = 'none';
                document.getElementById('matchCounter').style.display = 'none';
            }
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                if (data.success) {
                    if (data.results.length > 0 || window.searchMatches.length > 0) {
                        // 検索結果をタイプ別に分類
                        const byType = {
                            'id': [],
                            'class': [],
                            'tag': [],
                            'text': [],
                            'source': []
                        };
                        data.results.forEach(r => {
                            if (byType[r.type]) {
                                byType[r.type].push(r);
                            }
                        });
                        
                        let message = `検索結果: `;
                        if (window.searchMatches.length > 0) {
                            message += `ソース内に${window.searchMatches.length}箇所 `;
                        }
                        if (data.results.length > 0) {
                            message += `要素${data.results.length}個 `;
                        }
                        message += `見つかりました\n`;
                        
                        if (byType.id.length > 0) {
                            message += `ID: ${byType.id.length}個 `;
                        }
                        if (byType.class.length > 0) {
                            message += `クラス: ${byType.class.length}個 `;
                        }
                        if (byType.tag.length > 0) {
                            message += `タグ: ${byType.tag.length}個 `;
                        }
                        if (byType.text.length > 0) {
                            message += `テキスト: ${byType.text.length}個 `;
                        }
                        
                        // 詳細情報を表示（最初の5個まで）
                        const preview = data.results.slice(0, 5).map(r => {
                            let info = r.tag;
                            if (r.id) info += '#' + r.id;
                            if (r.class) info += '.' + r.class.split(' ')[0];
                            if (r.text) info += ' (' + r.text + ')';
                            return info;
                        }).join(', ');
                        if (preview) {
                            message += '\n' + preview;
                        }
                        
                        showStatus(message, 'success');
                    } else {
                        showStatus('要素が見つかりませんでした', 'error');
                    }
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        }
        
        // 検索モーダルを表示（グローバル関数として明示的に定義）
        window.showSearch = function showSearch() {
            const modal = document.getElementById('searchModal');
            if (modal) {
                modal.style.display = 'block';
            } else {
                console.error('検索モーダルが見つかりません');
            }
        };
        
        // 検索・置換を実行（グローバル関数として明示的に定義）
        window.performSearchReplace = function performSearchReplace() {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            const searchText = document.getElementById('searchText').value;
            const replaceText = document.getElementById('replaceText').value;
            
            if (!searchText) {
                showStatus('検索文字列を入力してください', 'error');
                return;
            }
            
            const content = editor.value;
            
            // 検索文字列をエスケープ（正規表現の特殊文字を処理）
            const escapedSearchText = searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedSearchText, 'g');
            
            if (regex.test(content)) {
                // 置換を実行
                const newContent = content.replace(regex, replaceText);
                editor.value = newContent;
                updatePreview();
                
                // 置換された箇所の数をカウント
                const matches = content.match(regex);
                const count = matches ? matches.length : 0;
                showStatus(`${count}箇所を置換しました`, 'success');
                closeModal('searchModal');
            } else {
                showStatus('検索文字列が見つかりませんでした', 'error');
            }
        };

        // デザイン出力モーダルを表示
        window.showDesignExport = function showDesignExport() {
            const modal = document.getElementById('designExportModal');
            if (modal) {
                modal.style.display = 'block';
            } else {
                showStatus('デザイン出力モーダルが見つかりません', 'error');
            }
        };
        
        // フォルダ履歴を保存
        function saveTemplateMergeDirHistory(dirPath) {
            if (!dirPath || dirPath.trim() === '') return;
            
            try {
                let history = JSON.parse(localStorage.getItem('templateMergeDirHistory') || '[]');
                // 既に存在する場合は削除
                history = history.filter(h => h !== dirPath);
                // 先頭に追加
                history.unshift(dirPath);
                // 最大10件まで保存
                history = history.slice(0, 10);
                localStorage.setItem('templateMergeDirHistory', JSON.stringify(history));
                updateTemplateMergeDirHistory();
            } catch (e) {
                console.error('履歴の保存に失敗しました:', e);
            }
        }
        
        // フォルダ履歴を更新
        function updateTemplateMergeDirHistory() {
            try {
                const history = JSON.parse(localStorage.getItem('templateMergeDirHistory') || '[]');
                const datalist = document.getElementById('templateMergeDirHistory');
                if (datalist) {
                    datalist.innerHTML = '';
                    history.forEach(dir => {
                        const option = document.createElement('option');
                        option.value = dir;
                        datalist.appendChild(option);
                    });
                }
            } catch (e) {
                console.error('履歴の読み込みに失敗しました:', e);
            }
        }
        
        // フォルダ選択ドロップダウンの変更処理
        function onTemplateMergeDirSelect() {
            const select = document.getElementById('templateMergeDirSelect');
            const dirInput = document.getElementById('templateMergeDir');
            
            if (select && dirInput) {
                const selectedValue = select.value;
                if (selectedValue === '__upload__') {
                    // アップロードフォルダを選択した場合、入力フィールドをクリア
                    dirInput.value = '';
                    loadTemplateFileList();
                } else if (selectedValue && selectedValue !== '') {
                    // その他のパスが選択された場合
                    dirInput.value = selectedValue;
                    loadTemplateFileList();
                } else {
                    // 選択が解除された場合、入力フィールドはそのまま
                    loadTemplateFileList();
                }
            }
        }
        
        // フォルダ選択ダイアログを表示（簡易版）
        function selectTemplateMergeDir() {
            const dirInput = document.getElementById('templateMergeDir');
            const select = document.getElementById('templateMergeDirSelect');
            if (dirInput) {
                const newPath = prompt('ディレクトリパスを入力してください:\n例: C:\\html または C:/html', dirInput.value || '');
                if (newPath !== null && newPath.trim() !== '') {
                    dirInput.value = newPath.trim();
                    if (select) {
                        select.value = '';
                    }
                    loadTemplateFileList();
                }
            }
        }
        
        // フォルダ選択ドロップダウンを更新
        function updateTemplateMergeDirSelect() {
            const select = document.getElementById('templateMergeDirSelect');
            const envOption = document.getElementById('templateMergeEnvOption');
            
            if (select) {
                // 履歴からオプションを追加
                try {
                    const history = JSON.parse(localStorage.getItem('templateMergeDirHistory') || '[]');
                    // 既存の履歴オプションを削除（環境変数オプション以外）
                    const existingOptions = Array.from(select.options);
                    existingOptions.forEach(opt => {
                        if (opt.value !== '' && opt.value !== '__upload__' && opt.value !== '__env__') {
                            opt.remove();
                        }
                    });
                    
                    // 履歴を追加
                    history.forEach(dir => {
                        const option = document.createElement('option');
                        option.value = dir;
                        option.textContent = `📁 ${dir}`;
                        // 環境変数オプションの前に挿入
                        if (envOption && envOption.parentNode) {
                            envOption.parentNode.insertBefore(option, envOption);
                        } else {
                            select.appendChild(option);
                        }
                    });
                } catch (e) {
                    console.error('履歴の読み込みに失敗しました:', e);
                }
                
                // 環境変数を確認
                // 環境変数オプションは常に非表示
                if (envOption) {
                    envOption.style.display = 'none';
                }
            }
        }
        
        // 現在の検索フォルダを表示
        function updateTemplateMergeCurrentDir(displayPath, source) {
            const currentDirDiv = document.getElementById('templateMergeCurrentDir');
            const currentDirPath = document.getElementById('templateMergeCurrentDirPath');
            if (currentDirDiv && currentDirPath) {
                if (displayPath) {
                    let displayText = displayPath;
                    let sourceText = '';
                    if (source === 'upload') {
                        sourceText = ' (アップロードフォルダ)';
                    } else if (source === 'user') {
                        sourceText = ' (ユーザー指定)';
                        // ユーザー指定の場合は履歴に保存
                        saveTemplateMergeDirHistory(displayPath);
                        // ドロップダウンも更新
                        updateTemplateMergeDirSelect();
                    }
                    currentDirPath.textContent = displayText + sourceText;
                    currentDirDiv.style.display = 'block';
                } else {
                    currentDirDiv.style.display = 'block';
                    currentDirPath.textContent = '未設定 - アップロードフォルダが使用されます';
                }
            }
        }
        
        // テンプレート統合の状態を保存
        function saveTemplateMergeState() {
            const state = {
                dirPath: document.getElementById('templateMergeDir')?.value || '',
                dirSelect: document.getElementById('templateMergeDirSelect')?.value || '__upload__',
                selectedFiles: Array.from(document.querySelectorAll('.template-file-checkbox:checked')).map(cb => {
                    return {
                        value: cb.value,
                        path: cb.getAttribute('data-path') || cb.value,
                        filename: cb.getAttribute('data-filename') || cb.value
                    };
                }),
                options: {
                    structure: document.getElementById('mergeOptionStructure')?.checked ?? true,
                    styles: document.getElementById('mergeOptionStyles')?.checked ?? true,
                    content: document.getElementById('mergeOptionContent')?.checked ?? true,
                    attributes: document.getElementById('mergeOptionAttributes')?.checked ?? true,
                    diffHandling: document.getElementById('mergeDiffHandling')?.value || 'common'
                }
            };
            localStorage.setItem('templateMergeState', JSON.stringify(state));
        }
        
        // テンプレート統合の状態を復元
        function restoreTemplateMergeState() {
            try {
                const saved = localStorage.getItem('templateMergeState');
                if (!saved) return false;
                
                const state = JSON.parse(saved);
                
                // ディレクトリパスと選択を復元
                const dirInput = document.getElementById('templateMergeDir');
                const dirSelect = document.getElementById('templateMergeDirSelect');
                if (dirInput && state.dirPath) {
                    dirInput.value = state.dirPath;
                }
                if (dirSelect && state.dirSelect) {
                    dirSelect.value = state.dirSelect;
                }
                
                // オプションを復元
                if (state.options) {
                    const structureCheck = document.getElementById('mergeOptionStructure');
                    const stylesCheck = document.getElementById('mergeOptionStyles');
                    const contentCheck = document.getElementById('mergeOptionContent');
                    const attributesCheck = document.getElementById('mergeOptionAttributes');
                    const diffHandlingSelect = document.getElementById('mergeDiffHandling');
                    
                    if (structureCheck) structureCheck.checked = state.options.structure;
                    if (stylesCheck) stylesCheck.checked = state.options.styles;
                    if (contentCheck) contentCheck.checked = state.options.content;
                    if (attributesCheck) attributesCheck.checked = state.options.attributes;
                    if (diffHandlingSelect && state.options.diffHandling) {
                        diffHandlingSelect.value = state.options.diffHandling;
                    }
                }
                
                return true;
            } catch (error) {
                console.error('テンプレート統合の状態復元エラー:', error);
                return false;
            }
        }
        
        // テンプレート統合モーダルを表示
        window.showTemplateMerge = function showTemplateMerge() {
            const modal = document.getElementById('templateMergeModal');
            if (modal) {
                modal.style.display = 'block';
                // フォルダ履歴を読み込み
                updateTemplateMergeDirHistory();
                // 環境変数オプションを更新
                updateTemplateMergeDirSelect();
                
                // 保存された状態を復元
                const restored = restoreTemplateMergeState();
                
                const dirInput = document.getElementById('templateMergeDir');
                const dirSelect = document.getElementById('templateMergeDirSelect');
                
                if (!restored) {
                    // 状態が保存されていない場合はデフォルト値を使用
                    if (dirInput) {
                        dirInput.value = '';
                    }
                    if (dirSelect) {
                        dirSelect.value = '__upload__'; // デフォルトでアップロードフォルダを選択
                    }
                }
                
                // 現在の検索フォルダ表示を更新
                if (dirInput && dirInput.value) {
                    updateTemplateMergeCurrentDir(dirInput.value, dirSelect?.value === '__upload__' ? 'upload' : 'user');
                } else {
                    updateTemplateMergeCurrentDir(null);
                }
                
                // ファイル一覧を読み込み
                loadTemplateFileList().then(() => {
                    // ファイル一覧読み込み後に選択状態を復元
                    try {
                        const saved = localStorage.getItem('templateMergeState');
                        if (saved) {
                            const state = JSON.parse(saved);
                            if (state.selectedFiles && state.selectedFiles.length > 0) {
                                // 少し遅延させてから復元（DOM更新を待つ）
                                setTimeout(() => {
                                    state.selectedFiles.forEach(fileInfo => {
                                        const checkbox = document.querySelector(`.template-file-checkbox[value="${fileInfo.value}"], .template-file-checkbox[data-path="${fileInfo.path}"]`);
                                        if (checkbox) {
                                            checkbox.checked = true;
                                        }
                                    });
                                }, 300);
                            }
                        }
                    } catch (error) {
                        console.error('ファイル選択状態の復元エラー:', error);
                    }
                });
            } else {
                showStatus('テンプレート統合モーダルが見つかりません', 'error');
            }
        };
        
        // テンプレート統合用のファイル一覧を読み込み
        window.loadTemplateFileList = async function loadTemplateFileList() {
            const fileListDiv = document.getElementById('templateFileList');
            if (!fileListDiv) return;
            
            const dirInput = document.getElementById('templateMergeDir');
            const dirSelect = document.getElementById('templateMergeDirSelect');
            let dirPath = dirInput ? dirInput.value.trim() : '';
            const selectedOption = dirSelect ? dirSelect.value : '';
            
            fileListDiv.innerHTML = '<p style="color: #718096; font-size: 12px; margin: 0;">読み込み中...</p>';
            
            try {
                let response;
                // ドロップダウンで「アップロードフォルダ」が明示的に選択されている場合、環境変数に関係なくアップロードフォルダから読み込む
                if (selectedOption === '__upload__') {
                    try {
                        const configResponse = await fetch('/api/config');
                        const configData = await configResponse.json();
                        const uploadFolder = configData.success ? configData.upload_folder : 'uploads';
                        updateTemplateMergeCurrentDir(uploadFolder, 'upload');
                        
                        const filesResponse = await fetch('/files');
                        const data = await filesResponse.json();
                        
                        if (data.success && data.files && data.files.length > 0) {
                            let html = '';
                            data.files.forEach(file => {
                                // HTMLファイルのみ表示
                                if (file.name.match(/\.html?$/i)) {
                                    html += `<label style="display: flex; align-items: center; gap: 8px; padding: 6px; cursor: pointer; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='#f0f4f8'" onmouseout="this.style.background='transparent'">`;
                                    html += `<input type="checkbox" class="template-file-checkbox" value="${file.name}" data-filename="${file.name}">`;
                                    html += `<span style="font-size: 12px;">${file.name}</span>`;
                                    html += `<span style="font-size: 11px; color: #718096;">(${file.size} bytes)</span>`;
                                    html += `</label>`;
                                }
                            });
                            if (html) {
                                fileListDiv.innerHTML = html;
                            } else {
                                fileListDiv.innerHTML = '<p style="color: #f56565; font-size: 12px; margin: 0;">HTMLファイルが見つかりませんでした</p>';
                            }
                        } else {
                            fileListDiv.innerHTML = '<p style="color: #f56565; font-size: 12px; margin: 0;">ファイルが見つかりませんでした</p>';
                        }
                    } catch (error) {
                        console.error('アップロードフォルダの読み込みエラー:', error);
                        fileListDiv.innerHTML = `<p style="color: #f56565; font-size: 12px; margin: 0;">エラー: ${error.message}</p>`;
                    }
                    return;
                }
                
                // ディレクトリパスが空で、選択もない場合はアップロードフォルダを確認
                if (!dirPath && !selectedOption) {
                    try {
                        const configResponse = await fetch('/api/config');
                        const configData = await configResponse.json();
                        // アップロードフォルダを読み込み
                        const uploadFolder = configData.success ? configData.upload_folder : 'uploads';
                        updateTemplateMergeCurrentDir(uploadFolder, 'upload');
                        
                        const filesResponse = await fetch('/files');
                        const data = await filesResponse.json();
                        
                        if (data.success && data.files && data.files.length > 0) {
                            let html = '';
                            data.files.forEach(file => {
                                // HTMLファイルのみ表示
                                if (file.name.match(/\.html?$/i)) {
                                    html += `<label style="display: flex; align-items: center; gap: 8px; padding: 6px; cursor: pointer; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='#f0f4f8'" onmouseout="this.style.background='transparent'">`;
                                    html += `<input type="checkbox" class="template-file-checkbox" value="${file.name}" data-filename="${file.name}">`;
                                    html += `<span style="font-size: 12px;">${file.name}</span>`;
                                    html += `<span style="font-size: 11px; color: #718096;">(${file.size} bytes)</span>`;
                                    html += `</label>`;
                                }
                            });
                            if (html) {
                                fileListDiv.innerHTML = html;
                            } else {
                                fileListDiv.innerHTML = '<p style="color: #f56565; font-size: 12px; margin: 0;">HTMLファイルが見つかりませんでした</p>';
                            }
                        } else {
                            fileListDiv.innerHTML = '<p style="color: #f56565; font-size: 12px; margin: 0;">ファイルが見つかりませんでした</p>';
                        }
                        return;
                    } catch (error) {
                        console.error('設定の読み込みエラー:', error);
                        fileListDiv.innerHTML = `<p style="color: #f56565; font-size: 12px; margin: 0;">エラー: ${error.message}</p>`;
                        return;
                    }
                }
                
                if (dirPath) {
                    // Windowsパスの正規化
                    let normalizedPath = dirPath.replace(/\\\\/g, '\\');
                    if (normalizedPath.match(/^[a-zA-Z]:/)) {
                        // ドライブレターを大文字に正規化
                        normalizedPath = normalizedPath[0].toUpperCase() + normalizedPath.substring(1).replace(/\//g, '\\');
                    }
                    
                    // 表示用のパスを更新（正規化前のパスを表示）
                    updateTemplateMergeCurrentDir(dirPath, 'user');
                    
                    // まずディレクトリの存在確認
                    const checkResponse = await fetch('/api/check-directory', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ directory: normalizedPath })
                    });
                    
                    const checkData = await checkResponse.json();
                    
                    if (!checkData.success || !checkData.exists) {
                        let errorMsg = checkData.error || 'ディレクトリが見つかりません';
                        if (checkData.suggestion) {
                            errorMsg += '\n' + checkData.suggestion;
                        }
                        if (checkData.parent_exists && checkData.parent_path) {
                            errorMsg += `\n親ディレクトリ（${checkData.parent_path}）は存在します。`;
                        }
                        // アップロードフォルダを使用する方法を案内
                        errorMsg += '\n\n💡 ヒント: ドロップダウンから「📁 アップロードフォルダ」を選択すると、アップロードしたファイルを表示できます。';
                        fileListDiv.innerHTML = `<p style="color: #f56565; font-size: 12px; margin: 0; white-space: pre-line;">${errorMsg}</p>`;
                        return;
                    }
                    
                    // ディレクトリが存在する場合、ファイル一覧を取得
                    response = await fetch('/api/list-directory-files', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ directory: normalizedPath })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success && data.files && data.files.length > 0) {
                        let html = '';
                        // HTMLファイルのみ表示
                        data.files.filter(file => file.type === 'html').forEach(file => {
                            html += `<label style="display: flex; align-items: center; gap: 8px; padding: 6px; cursor: pointer; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='#f0f4f8'" onmouseout="this.style.background='transparent'">`;
                            html += `<input type="checkbox" class="template-file-checkbox" value="${file.path || file.name}" data-filename="${file.name}" data-path="${file.path || file.name}">`;
                            html += `<span style="font-size: 12px;">${file.name}</span>`;
                            html += `<span style="font-size: 11px; color: #718096;">(${file.size} bytes)</span>`;
                            html += `</label>`;
                        });
                        if (html) {
                            fileListDiv.innerHTML = html;
                        } else {
                            fileListDiv.innerHTML = '<p style="color: #f56565; font-size: 12px; margin: 0;">HTMLファイルが見つかりませんでした</p>';
                        }
                    } else {
                        fileListDiv.innerHTML = `<p style="color: #f56565; font-size: 12px; margin: 0;">${data.error || 'ファイルが見つかりませんでした'}</p>`;
                    }
                }
            } catch (error) {
                fileListDiv.innerHTML = `<p style="color: #f56565; font-size: 12px; margin: 0;">エラー: ${error.message}</p>`;
            }
        };
        
        // テンプレート統合を実行
        window.performTemplateMerge = async function performTemplateMerge() {
            const checkboxes = document.querySelectorAll('.template-file-checkbox:checked');
            if (checkboxes.length < 2) {
                showStatus('統合には2つ以上のファイルを選択してください', 'error');
                return;
            }
            
            // ファイルパスを取得（data-path属性があればそれを使用、なければvalueを使用）
            const selectedFiles = Array.from(checkboxes).map(cb => {
                const filePath = cb.getAttribute('data-path');
                return filePath || cb.value;
            });
            const mergeOptions = {
                structure: document.getElementById('mergeOptionStructure').checked,
                styles: document.getElementById('mergeOptionStyles').checked,
                content: document.getElementById('mergeOptionContent').checked,
                attributes: document.getElementById('mergeOptionAttributes').checked,
                diffHandling: document.getElementById('mergeDiffHandling').value
            };
            
            // 状態を保存
            saveTemplateMergeState();
            
            const progressDiv = document.getElementById('templateMergeProgress');
            const progressBar = document.getElementById('templateMergeProgressBar');
            const resultDiv = document.getElementById('templateMergeResult');
            const resultContent = document.getElementById('templateMergeResultContent');
            const performBtn = document.getElementById('performMergeBtn');
            const downloadBtn = document.getElementById('downloadMergedBtn');
            
            progressDiv.style.display = 'block';
            progressBar.style.width = '0%';
            resultDiv.style.display = 'none';
            downloadBtn.style.display = 'none';
            performBtn.disabled = true;
            
            try {
                progressBar.style.width = '30%';
                
                const response = await fetch('/template-merge', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        files: selectedFiles,
                        options: mergeOptions
                    })
                });
                
                progressBar.style.width = '70%';
                
                const data = await response.json();
                
                progressBar.style.width = '100%';
                
                if (data.success) {
                    window.mergedTemplateContent = data.template;
                    window.mergedTemplateStats = data.stats;
                    
                    let statsHtml = '<div style="margin-bottom: 10px;">';
                    statsHtml += `<strong>統合完了</strong><br>`;
                    statsHtml += `ファイル数: ${selectedFiles.length}個<br>`;
                    statsHtml += `共通要素: ${data.stats.commonElements}個<br>`;
                    statsHtml += `差異要素: ${data.stats.diffElements}個<br>`;
                    statsHtml += `統合要素: ${data.stats.mergedElements}個<br>`;
                    statsHtml += '</div>';
                    
                    if (data.stats.differences && data.stats.differences.length > 0) {
                        statsHtml += '<div style="margin-top: 10px;"><strong>主な差異:</strong><ul style="margin: 5px 0; padding-left: 20px; font-size: 11px;">';
                        data.stats.differences.slice(0, 10).forEach(diff => {
                            statsHtml += `<li>${diff}</li>`;
                        });
                        if (data.stats.differences.length > 10) {
                            statsHtml += `<li>...他 ${data.stats.differences.length - 10}件</li>`;
                        }
                        statsHtml += '</ul></div>';
                    }
                    
                    resultContent.innerHTML = statsHtml;
                    resultDiv.style.display = 'block';
                    downloadBtn.style.display = 'inline-block';
                    showStatus('テンプレート統合が完了しました', 'success');
                } else {
                    resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${data.error}</p>`;
                    resultDiv.style.display = 'block';
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${error.message}</p>`;
                resultDiv.style.display = 'block';
                showStatus('エラー: ' + error.message, 'error');
            } finally {
                performBtn.disabled = false;
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 500);
            }
        };
        
        // 統合されたテンプレートをダウンロード
        window.downloadMergedTemplate = function downloadMergedTemplate() {
            if (!window.mergedTemplateContent) {
                showStatus('統合テンプレートがありません', 'error');
                return;
            }
            
            const blob = new Blob([window.mergedTemplateContent], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'merged_template_' + new Date().toISOString().slice(0, 10) + '.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showStatus('統合テンプレートをダウンロードしました', 'success');
        };
        
        // 差分検出モーダルを表示
        window.showDiffAnalysis = async function showDiffAnalysis() {
            const modal = document.getElementById('diffAnalysisModal');
            if (modal) {
                modal.style.display = 'block';
                
                // 入力フィールドを確実にクリア（アップロードフォルダを使用）
                const dirInput = document.getElementById('diffAnalysisDir');
                if (dirInput) {
                    dirInput.value = '';
                }
                
                // エラーメッセージをクリア
                const resultDiv = document.getElementById('diffAnalysisResult');
                if (resultDiv) {
                    resultDiv.style.display = 'none';
                }
                
                // 環境変数を確認してディレクトリ情報を表示
                await updateDiffAnalysisDirInfo();
            } else {
                showStatus('差分検出モーダルが見つかりません', 'error');
            }
        };
        
        // 差分検出のディレクトリ情報を更新
        window.updateDiffAnalysisDirInfo = async function updateDiffAnalysisDirInfo() {
            const dirInfoDiv = document.getElementById('diffAnalysisDirInfo');
            const dirPathDiv = document.getElementById('diffAnalysisDirPath');
            const dirFilesDiv = document.getElementById('diffAnalysisDirFiles');
            const fileListDiv = document.getElementById('diffAnalysisFileList');
            const fileListContent = document.getElementById('diffAnalysisFileListContent');
            const dirInput = document.getElementById('diffAnalysisDir');
            
            if (!dirInfoDiv || !dirPathDiv || !dirFilesDiv) return;
            
            // 入力フィールドの値を確認
            const inputValue = dirInput ? dirInput.value.trim() : '';
            
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                
                // 入力フィールドが空欄の場合、アップロードフォルダを使用
                if (!inputValue) {
                    // アップロードフォルダを使用
                    const uploadFolder = data.success ? data.upload_folder : 'uploads';
                    dirPathDiv.textContent = uploadFolder + ' (アップロードフォルダ)';
                    
                    // アップロードフォルダのファイル一覧を取得
                    try {
                        const filesResponse = await fetch('/files');
                        const filesData = await filesResponse.json();
                        
                        if (filesData.success && filesData.files && filesData.files.length > 0) {
                            const htmlFiles = filesData.files.filter(f => 
                                f.name.toLowerCase().endsWith('.html') || 
                                f.name.toLowerCase().endsWith('.htm')
                            );
                            
                            if (htmlFiles.length > 0) {
                                dirFilesDiv.textContent = `✅ ${htmlFiles.length}件のHTMLファイルが見つかりました`;
                                dirFilesDiv.style.color = '#48bb78';
                                
                                // HTMLファイル一覧を表示
                                if (fileListDiv && fileListContent) {
                                    fileListContent.innerHTML = '';
                                    htmlFiles.forEach((file, index) => {
                                        const sizeKB = (file.size / 1024).toFixed(1);
                                        const fileItem = document.createElement('div');
                                        fileItem.style.padding = '4px 0';
                                        fileItem.style.borderBottom = index < htmlFiles.length - 1 ? '1px solid #e2e8f0' : 'none';
                                        fileItem.innerHTML = `<span style="color: #667eea;">📄</span> ${file.name} <span style="color: #718096;">(${sizeKB} KB)</span>`;
                                        fileListContent.appendChild(fileItem);
                                    });
                                    fileListDiv.style.display = 'block';
                                }
                            } else {
                                dirFilesDiv.textContent = '⚠️ アップロードフォルダにHTMLファイルが見つかりませんでした';
                                dirFilesDiv.style.color = '#f59e0b';
                                if (fileListDiv) {
                                    fileListDiv.style.display = 'none';
                                }
                            }
                        } else {
                            dirFilesDiv.textContent = '⚠️ アップロードフォルダにファイルが見つかりませんでした';
                            dirFilesDiv.style.color = '#f59e0b';
                            if (fileListDiv) {
                                fileListDiv.style.display = 'none';
                            }
                        }
                    } catch (error) {
                        dirFilesDiv.textContent = 'ℹ️ アップロードフォルダの情報を確認中...';
                        dirFilesDiv.style.color = '#718096';
                        if (fileListDiv) {
                            fileListDiv.style.display = 'none';
                        }
                    }
                    dirInfoDiv.style.display = 'block';
                } else {
                    // 入力フィールドに値が入力されている場合、ディレクトリ情報を確認
                    if (data.success && data.directory_info) {
                        const dirInfo = data.directory_info;
                        if (dirInfo.exists) {
                            dirPathDiv.textContent = dirInfo.path;
                            
                            // HTMLファイルのみをフィルタリング
                            const htmlFiles = dirInfo.files.filter(f => 
                                f.name.toLowerCase().endsWith('.html') || 
                                f.name.toLowerCase().endsWith('.htm')
                            );
                            
                            if (htmlFiles.length > 0) {
                                dirFilesDiv.textContent = `✅ ${htmlFiles.length}件のHTMLファイルが見つかりました`;
                                dirFilesDiv.style.color = '#48bb78';
                                
                                // HTMLファイル一覧を表示
                                if (fileListDiv && fileListContent) {
                                    fileListContent.innerHTML = '';
                                    htmlFiles.forEach((file, index) => {
                                        const sizeKB = (file.size / 1024).toFixed(1);
                                        const fileItem = document.createElement('div');
                                        fileItem.style.padding = '4px 0';
                                        fileItem.style.borderBottom = index < htmlFiles.length - 1 ? '1px solid #e2e8f0' : 'none';
                                        fileItem.innerHTML = `<span style="color: #667eea;">📄</span> ${file.name} <span style="color: #718096;">(${sizeKB} KB)</span>`;
                                        fileListContent.appendChild(fileItem);
                                    });
                                    fileListDiv.style.display = 'block';
                                }
                            } else {
                                dirFilesDiv.textContent = '⚠️ ディレクトリは存在しますが、HTMLファイルが見つかりませんでした';
                                dirFilesDiv.style.color = '#f59e0b';
                                if (fileListDiv) {
                                    fileListDiv.style.display = 'none';
                                }
                            }
                            dirInfoDiv.style.display = 'block';
                        } else {
                            dirPathDiv.textContent = dirInfo.path || inputValue;
                            dirFilesDiv.textContent = '❌ ディレクトリが存在しません\n\n💡 ヒント: パスを空欄にすると、アップロードフォルダが使用されます。';
                            dirFilesDiv.style.color = '#ef4444';
                            if (fileListDiv) {
                                fileListDiv.style.display = 'none';
                            }
                            dirInfoDiv.style.display = 'block';
                        }
                    } else {
                        // 入力されたパスを表示（存在確認を試みる）
                        dirPathDiv.textContent = inputValue + ' (ユーザー指定)';
                        
                        // ディレクトリの存在確認を試みる
                        try {
                            const checkResponse = await fetch('/api/check-directory', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ directory: inputValue })
                            });
                            
                            const checkData = await checkResponse.json();
                            
                            if (checkData.success && checkData.exists) {
                                if (checkData.file_count > 0) {
                                    dirFilesDiv.textContent = `✅ ${checkData.file_count}件のファイルが見つかりました`;
                                    dirFilesDiv.style.color = '#48bb78';
                                } else {
                                    dirFilesDiv.textContent = '⚠️ ディレクトリは存在しますが、ファイルが見つかりませんでした';
                                    dirFilesDiv.style.color = '#f59e0b';
                                }
                            } else {
                                dirFilesDiv.textContent = '❌ ディレクトリが存在しません';
                                dirFilesDiv.style.color = '#ef4444';
                                if (checkData.suggestion) {
                                    dirFilesDiv.textContent += '\n' + checkData.suggestion;
                                }
                                dirFilesDiv.textContent += '\n\n💡 ヒント: パスを空欄にすると、アップロードフォルダが使用されます。';
                            }
                        } catch (error) {
                            dirFilesDiv.textContent = 'ℹ️ 実行時にディレクトリの存在を確認します';
                            dirFilesDiv.style.color = '#718096';
                        }
                        if (fileListDiv) {
                            fileListDiv.style.display = 'none';
                        }
                        dirInfoDiv.style.display = 'block';
                    }
                }
            } catch (error) {
                console.error('ディレクトリ情報の取得エラー:', error);
                dirInfoDiv.style.display = 'none';
            }
        }
        
        // 差分検出を実行
        window.performDiffAnalysis = async function performDiffAnalysis() {
            let dirPath = document.getElementById('diffAnalysisDir').value.trim();
            if (!dirPath) {
                // 空欄の場合はアップロードフォルダを使用
                dirPath = '__upload__';
            }
            
            // Windowsパスの正規化
            // バックスラッシュのエスケープを処理（c:\\html -> c:\html）
            dirPath = dirPath.replace(/\\\\/g, '\\');
            
            // スラッシュをバックスラッシュに変換（Windowsの場合）
            if (dirPath.match(/^[a-zA-Z]:/)) {
                // Windowsのドライブレターがある場合
                // ドライブレターを大文字に正規化
                dirPath = dirPath[0].toUpperCase() + dirPath.substring(1).replace(/\//g, '\\');
            }
            
            const options = {
                structure: document.getElementById('diffOptionStructure').checked,
                styles: document.getElementById('diffOptionStyles').checked,
                content: document.getElementById('diffOptionContent').checked,
                attributes: document.getElementById('diffOptionAttributes').checked,
                detailed: document.getElementById('diffOptionDetailed').checked
            };
            
            const progressDiv = document.getElementById('diffAnalysisProgress');
            const progressBar = document.getElementById('diffAnalysisProgressBar');
            const progressText = document.getElementById('diffProgressText');
            const resultDiv = document.getElementById('diffAnalysisResult');
            const resultContent = document.getElementById('diffAnalysisResultContent');
            const performBtn = document.getElementById('performDiffBtn');
            const downloadBtn = document.getElementById('downloadDiffBtn');
            const exportCSVBtn = document.getElementById('exportDiffCSVBtn');
            
            progressDiv.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = '処理中...';
            resultDiv.style.display = 'none';
            downloadBtn.style.display = 'none';
            exportCSVBtn.style.display = 'none';
            performBtn.disabled = true;
            
            try {
                progressBar.style.width = '20%';
                progressText.textContent = 'ディレクトリを読み込み中...';
                
                // タイムアウト設定（90秒）
                const timeoutMs = 90000;
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
                
                let response;
                try {
                    response = await fetch('/diff-analysis', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            directory: dirPath,
                            options: options
                        }),
                        signal: controller.signal
                    });
                    clearTimeout(timeoutId);
                } catch (error) {
                    clearTimeout(timeoutId);
                    if (error.name === 'AbortError') {
                        throw new Error('リクエストがタイムアウトしました（90秒）。処理に時間がかかりすぎています。ファイル数や要素数を減らして再試行してください。');
                    }
                    throw error;
                }
                
                progressBar.style.width = '80%';
                progressText.textContent = '差分を分析中...';
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: 'サーバーエラーが発生しました' }));
                    throw new Error(errorData.error || `HTTPエラー: ${response.status}`);
                }
                
                const data = await response.json();
                
                progressBar.style.width = '100%';
                progressText.textContent = '完了！';
                
                if (data.success) {
                    window.diffAnalysisData = data;
                    window.diffAnalysisData.directory = dirPath;  // ディレクトリパスを保存
                    
                    // 結果を表示
                    let html = '<div style="margin-bottom: 15px;">';
                    html += `<h3 style="font-size: 16px; margin-bottom: 10px; color: var(--text-primary);">📊 分析結果サマリー</h3>`;
                    html += `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 15px;">`;
                    html += `<div style="padding: 12px; background: white; border-radius: 8px; border: 1px solid var(--border-color);">`;
                    html += `<div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">分析ファイル数</div>`;
                    html += `<div style="font-size: 24px; font-weight: 700; color: var(--primary-color);">${data.summary.totalFiles}</div>`;
                    html += `</div>`;
                    html += `<div style="padding: 12px; background: white; border-radius: 8px; border: 1px solid var(--border-color);">`;
                    html += `<div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">構造差分</div>`;
                    html += `<div style="font-size: 24px; font-weight: 700; color: var(--warning-color);">${data.summary.structureDiffs}</div>`;
                    html += `</div>`;
                    html += `<div style="padding: 12px; background: white; border-radius: 8px; border: 1px solid var(--border-color);">`;
                    html += `<div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">スタイル差分</div>`;
                    html += `<div style="font-size: 24px; font-weight: 700; color: var(--info-color);">${data.summary.styleDiffs}</div>`;
                    html += `</div>`;
                    html += `<div style="padding: 12px; background: white; border-radius: 8px; border: 1px solid var(--border-color);">`;
                    html += `<div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">コンテンツ差分</div>`;
                    html += `<div style="font-size: 24px; font-weight: 700; color: var(--danger-color);">${data.summary.contentDiffs}</div>`;
                    html += `</div>`;
                    html += `</div>`;
                    html += `</div>`;
                    
                    // システムメッセージ（タイムアウトや制限）をチェック
                    const systemMessages = data.differences ? data.differences.filter(d => d.type === 'system') : [];
                    const actualDifferences = data.differences ? data.differences.filter(d => d.type !== 'system') : [];
                    
                    if (systemMessages.length > 0) {
                        html += '<div style="margin-top: 20px; padding: 12px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;">';
                        html += '<h3 style="font-size: 14px; margin-bottom: 8px; color: #856404;">⚠️ 処理情報</h3>';
                        systemMessages.forEach(msg => {
                            html += `<div style="font-size: 12px; color: #856404; margin-bottom: 4px;">${msg.description}</div>`;
                        });
                        html += '</div>';
                    }
                    
                    if (actualDifferences.length > 0) {
                        html += '<h3 style="font-size: 16px; margin-bottom: 10px; margin-top: 20px; color: var(--text-primary);">🔍 検出された差分</h3>';
                        html += '<div style="display: flex; flex-direction: column; gap: 8px;">';
                        
                        actualDifferences.forEach((diff, index) => {
                            const typeColors = {
                                'structure': '#f59e0b',
                                'style': '#3b82f6',
                                'content': '#ef4444',
                                'attribute': '#8b5cf6',
                                'system': '#6c757d'
                            };
                            const typeLabels = {
                                'structure': '構造',
                                'style': 'スタイル',
                                'content': 'コンテンツ',
                                'attribute': '属性',
                                'system': 'システム'
                            };
                            
                            html += `<div style="padding: 12px; background: white; border-radius: 8px; border-left: 4px solid ${typeColors[diff.type] || '#666'}; box-shadow: var(--shadow-sm);">`;
                            html += `<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 6px;">`;
                            html += `<div style="font-weight: 600; color: var(--text-primary); font-size: 13px;">`;
                            html += `<span style="display: inline-block; padding: 2px 8px; background: ${typeColors[diff.type] || '#666'}; color: white; border-radius: 4px; font-size: 11px; margin-right: 8px;">${typeLabels[diff.type] || diff.type}</span>`;
                            html += `${diff.element || diff.selector || '不明な要素'}`;
                            html += `</div>`;
                            html += `<div style="font-size: 11px; color: var(--text-tertiary);">${diff.files ? diff.files.length + 'ファイル' : ''}</div>`;
                            html += `</div>`;
                            if (diff.description) {
                                html += `<div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${diff.description}</div>`;
                            }
                            if (diff.files && diff.files.length > 0) {
                                html += `<div style="font-size: 11px; color: var(--text-tertiary); margin-top: 6px;">影響ファイル: ${diff.files.join(', ')}</div>`;
                            }
                            html += `</div>`;
                        });
                        
                        html += '</div>';
                    } else if (!systemMessages.length) {
                        html += '<div style="margin-top: 20px; padding: 12px; background: #d1ecf1; border: 1px solid #bee5eb; border-radius: 8px;">';
                        html += '<p style="font-size: 12px; color: #0c5460; margin: 0;">✅ 差分は検出されませんでした。すべてのファイルが同じ構造を持っています。</p>';
                        html += '</div>';
                    }
                    
                    resultContent.innerHTML = html;
                    resultDiv.style.display = 'block';
                    downloadBtn.style.display = 'inline-block';
                    exportCSVBtn.style.display = 'inline-block';
                    showStatus('差分検出が完了しました', 'success');
                } else {
                    const errorMsg = data.error || '差分検出に失敗しました';
                    resultContent.innerHTML = `
                        <div style="color: #f56565; padding: 15px; background: #fee; border: 1px solid #fcc; border-radius: 8px;">
                            <p style="margin: 0 0 10px 0; font-weight: 600; font-size: 14px;">エラー: ${errorMsg}</p>
                            ${errorMsg.includes('ディレクトリが見つかりません') ? `
                                <p style="margin: 0; font-size: 12px; color: #666;">
                                    パスの例: C:\\html または C:/html<br>
                                    絶対パスを指定してください
                                </p>
                            ` : ''}
                        </div>
                    `;
                    resultDiv.style.display = 'block';
                    showStatus('エラー: ' + errorMsg, 'error');
                }
            } catch (error) {
                const errorMsg = error.message || '差分検出中にエラーが発生しました';
                resultContent.innerHTML = `
                    <div style="color: #f56565; padding: 15px; background: #fee; border: 1px solid #fcc; border-radius: 8px;">
                        <p style="margin: 0 0 10px 0; font-weight: 600; font-size: 14px;">エラー: ${errorMsg}</p>
                        <p style="margin: 0; font-size: 12px; color: #666;">
                            パスの例: C:\\html または C:/html<br>
                            絶対パスを指定してください
                        </p>
                    </div>
                `;
                resultDiv.style.display = 'block';
                showStatus('エラー: ' + errorMsg, 'error');
            } finally {
                performBtn.disabled = false;
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 500);
            }
        };
        
        // 差分レポートをダウンロード
        window.downloadDiffReport = function downloadDiffReport() {
            if (!window.diffAnalysisData) {
                showStatus('差分データがありません', 'error');
                return;
            }
            
            const report = JSON.stringify(window.diffAnalysisData, null, 2);
            const blob = new Blob([report], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'diff_report_' + new Date().toISOString().slice(0, 10) + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showStatus('差分レポートをダウンロードしました', 'success');
        };
        
        // 差分をCSVでエクスポート
        window.exportDiffToCSV = function exportDiffToCSV() {
            if (!window.diffAnalysisData || !window.diffAnalysisData.differences) {
                showStatus('差分データがありません', 'error');
                return;
            }
            
            let csv = 'タイプ,要素,説明,影響ファイル数,影響ファイル\n';
            window.diffAnalysisData.differences.forEach(diff => {
                const type = diff.type || '';
                const element = (diff.element || diff.selector || '').replace(/"/g, '""');
                const description = (diff.description || '').replace(/"/g, '""');
                const fileCount = diff.files ? diff.files.length : 0;
                const files = (diff.files || []).join('; ').replace(/"/g, '""');
                csv += `"${type}","${element}","${description}",${fileCount},"${files}"\n`;
            });
            
            const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'diff_report_' + new Date().toISOString().slice(0, 10) + '.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showStatus('CSVファイルをダウンロードしました', 'success');
        };
        
        // 最大公約数テンプレートを生成
        window.generateGCDTemplate = async function generateGCDTemplate() {
            if (!window.diffAnalysisData || !window.diffAnalysisData.directory) {
                showStatus('先に差分検出を実行してください', 'error');
                return;
            }
            
            const dirPath = document.getElementById('diffAnalysisDir').value.trim();
            if (!dirPath) {
                showStatus('ディレクトリパスが設定されていません', 'error');
                return;
            }
            
            const options = {
                structure: document.getElementById('diffOptionStructure').checked,
                styles: document.getElementById('diffOptionStyles').checked,
                content: document.getElementById('diffOptionContent').checked,
                attributes: document.getElementById('diffOptionAttributes').checked,
                detailed: document.getElementById('diffOptionDetailed').checked
            };
            
            const resultDiv = document.getElementById('gcdTemplateResult');
            const resultContent = document.getElementById('gcdTemplateResultContent');
            const downloadBtn = document.getElementById('downloadGCDBtn');
            
            resultDiv.style.display = 'block';
            resultContent.innerHTML = '<p>最大公約数テンプレートを生成中...</p>';
            downloadBtn.style.display = 'none';
            
            try {
                const response = await fetch('/gcd-template', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        directory: dirPath,
                        options: options
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    window.gcdTemplateContent = data.template;
                    window.gcdTemplateStats = data.stats;
                    
                    let html = '<div style="margin-bottom: 15px;">';
                    html += `<strong>最大公約数テンプレート生成完了</strong><br>`;
                    html += `ファイル数: ${data.stats.totalFiles}個<br>`;
                    html += `共通要素: ${data.stats.commonElements}個<br>`;
                    html += `変数化された要素: ${data.stats.variableElements}個<br>`;
                    html += `統合要素: ${data.stats.mergedElements}個<br>`;
                    html += '</div>';
                    
                    if (data.stats.variables && data.stats.variables.length > 0) {
                        html += '<div style="margin-top: 15px;"><strong>変数化された部分:</strong><ul style="margin: 5px 0; padding-left: 20px; font-size: 11px;">';
                        data.stats.variables.slice(0, 20).forEach(v => {
                            html += `<li>${v.name}: ${v.description}</li>`;
                        });
                        if (data.stats.variables.length > 20) {
                            html += `<li>...他 ${data.stats.variables.length - 20}件</li>`;
                        }
                        html += '</ul></div>';
                    }
                    
                    resultContent.innerHTML = html;
                    downloadBtn.style.display = 'inline-block';
                    showStatus('最大公約数テンプレートを生成しました', 'success');
                } else {
                    resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${data.error}</p>`;
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${error.message}</p>`;
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // 最大公約数テンプレートをダウンロード
        window.downloadGCDTemplate = function downloadGCDTemplate() {
            if (!window.gcdTemplateContent) {
                showStatus('テンプレートがありません', 'error');
                return;
            }
            
            const blob = new Blob([window.gcdTemplateContent], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'gcd_template_' + new Date().toISOString().slice(0, 10) + '.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showStatus('最大公約数テンプレートをダウンロードしました', 'success');
        };
        
        // 27大学のホームページを生成
        window.generateUniversityPages = async function generateUniversityPages() {
            if (!window.gcdTemplateContent || !window.diffAnalysisData || !window.diffAnalysisData.directory) {
                showStatus('先に最大公約数テンプレートを生成してください', 'error');
                return;
            }
            
            const dirPath = document.getElementById('diffAnalysisDir').value.trim();
            if (!dirPath) {
                showStatus('ディレクトリパスが設定されていません', 'error');
                return;
            }
            
            const resultDiv = document.getElementById('universityPagesResult');
            const resultContent = document.getElementById('universityPagesResultContent');
            const downloadBtn = document.getElementById('downloadUnivPagesBtn');
            
            resultDiv.style.display = 'block';
            resultContent.innerHTML = '<p>27大学のホームページを生成中...</p>';
            downloadBtn.style.display = 'none';
            
            try {
                const response = await fetch('/generate-university-pages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        directory: dirPath,
                        template: window.gcdTemplateContent
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    window.universityPagesData = data;
                    
                    let html = '<div style="margin-bottom: 15px;">';
                    html += `<strong>27大学のホームページ生成完了</strong><br>`;
                    html += `生成ファイル数: ${data.generatedFiles}個<br>`;
                    html += `成功: ${data.successCount}個<br>`;
                    if (data.failedCount > 0) {
                        html += `失敗: ${data.failedCount}個<br>`;
                    }
                    html += '</div>';
                    
                    if (data.files && data.files.length > 0) {
                        html += '<div style="margin-top: 15px;"><strong>生成されたファイル:</strong><ul style="margin: 5px 0; padding-left: 20px; font-size: 11px; max-height: 200px; overflow-y: auto;">';
                        data.files.forEach(file => {
                            html += `<li>${file}</li>`;
                        });
                        html += '</ul></div>';
                    }
                    
                    resultContent.innerHTML = html;
                    downloadBtn.style.display = 'inline-block';
                    showStatus('27大学のホームページを生成しました', 'success');
                } else {
                    resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${data.error}</p>`;
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                resultContent.innerHTML = `<p style="color: #f56565;">エラー: ${error.message}</p>`;
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // 27大学のホームページをZIPでダウンロード
        window.downloadUniversityPages = async function downloadUniversityPages() {
            if (!window.universityPagesData || !window.universityPagesData.directory) {
                showStatus('生成データがありません', 'error');
                return;
            }
            
            try {
                const response = await fetch('/download-university-pages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        directory: window.universityPagesData.directory
                    })
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'university_pages_' + new Date().toISOString().slice(0, 10) + '.zip';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    
                    showStatus('ZIPファイルをダウンロードしました', 'success');
                } else {
                    const data = await response.json();
                    showStatus('エラー: ' + (data.error || 'ダウンロードに失敗しました'), 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        };

        // 画面デザイン差分を確認しやすいように、プレビューDOMの主要スタイルをJSON/CSVで出力
        window.performDesignExport = function performDesignExport() {
            const preview = document.getElementById('preview');
            if (!preview) {
                showStatus('プレビューが見つかりません', 'error');
                return;
            }

            let previewDoc;
            try {
                previewDoc = preview.contentDocument || preview.contentWindow.document;
            } catch (e) {
                showStatus('プレビューDOMにアクセスできません（セキュリティ制限）', 'error');
                return;
            }
            if (!previewDoc || !previewDoc.documentElement) {
                showStatus('プレビューがまだ読み込まれていません', 'error');
                return;
            }

            const format = (document.getElementById('designExportFormat')?.value || 'json').toLowerCase();
            const scope = (document.getElementById('designExportScope')?.value || 'all').toLowerCase();
            const maxNodes = Math.min(
                Math.max(parseInt(document.getElementById('designExportMaxNodes')?.value || '3000', 10) || 3000, 100),
                20000
            );

            // 比較に使うプロパティ（必要なら増やせます）
            const STYLE_KEYS = [
                'display', 'position', 'zIndex',
                'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'textAlign',
                'color', 'backgroundColor',
                'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
                'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
                'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
                'borderTopStyle', 'borderRightStyle', 'borderBottomStyle', 'borderLeftStyle',
                'borderTopColor', 'borderRightColor', 'borderBottomColor', 'borderLeftColor',
                'borderRadius',
                'width', 'height',
            ];

            function getSelector(el) {
                if (!el || el.nodeType !== 1) return '';
                if (el.id) return `#${el.id}`;
                const parts = [];
                let node = el;
                let depth = 0;
                while (node && node.nodeType === 1 && depth < 5) {
                    const tag = node.tagName.toLowerCase();
                    const cls = (node.className && typeof node.className === 'string')
                        ? node.className.trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.')
                        : '';
                    // nth-of-type を付けて曖昧さを減らす
                    let idx = 1;
                    if (node.parentElement) {
                        const siblings = Array.from(node.parentElement.children).filter(c => c.tagName === node.tagName);
                        idx = siblings.indexOf(node) + 1;
                    }
                    parts.unshift(`${tag}${cls ? '.' + cls : ''}:nth-of-type(${idx})`);
                    node = node.parentElement;
                    depth++;
                }
                return parts.join(' > ');
            }

            function getNodesByScope() {
                if (scope === 'form') {
                    return Array.from(previewDoc.querySelectorAll('label, input, select, textarea, button'));
                }
                if (scope === 'label') {
                    // label と、forで紐づく要素、隣接要素を含める
                    const set = new Set();
                    const labels = Array.from(previewDoc.querySelectorAll('label'));
                    for (const lb of labels) {
                        set.add(lb);
                        const forId = lb.getAttribute('for');
                        if (forId) {
                            const t = previewDoc.getElementById(forId);
                            if (t) set.add(t);
                        }
                        if (lb.nextElementSibling) set.add(lb.nextElementSibling);
                    }
                    return Array.from(set);
                }
                return Array.from(previewDoc.querySelectorAll('body *'));
            }

            // 要素数が多いページ向けに上限
            const nodes = getNodesByScope().slice(0, maxNodes);

            const snapshot = {
                meta: {
                    generatedAt: new Date().toISOString(),
                    filename: window.editorFilename || '',
                    url: preview.src || '',
                    nodeCount: nodes.length,
                    maxNodes: maxNodes,
                    scope,
                    format,
                },
                nodes: [],
            };

            for (const el of nodes) {
                const cs = previewDoc.defaultView.getComputedStyle(el);
                const style = {};
                for (const k of STYLE_KEYS) style[k] = cs[k];

                // テキストは差分比較のノイズになりやすいので短く
                const text = (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80);

                const rect = el.getBoundingClientRect();
                snapshot.nodes.push({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    class: (el.className && typeof el.className === 'string') ? el.className : '',
                    selector: getSelector(el),
                    text,
                    rect: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height),
                    },
                    style,
                });
            }

            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
            const base = (window.editorFilename && window.editorFilename.trim() !== '')
                ? window.editorFilename.replace(/\.html?$/i, '')
                : 'design';

            function downloadText(text, mime, filename) {
                const blob = new Blob([text], { type: mime });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }

            if (format === 'csv') {
                // CSVは列を固定して比較しやすくする（styleは主要項目のみフラット化）
                const cols = [
                    'selector','tag','id','class','text','x','y','w','h',
                    ...STYLE_KEYS.map(k => `style.${k}`)
                ];
                const esc = (v) => {
                    const s = String(v ?? '');
                    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
                };
                const rows = [cols.join(',')];
                for (const n of snapshot.nodes) {
                    const row = [];
                    row.push(n.selector);
                    row.push(n.tag);
                    row.push(n.id);
                    row.push(n.class);
                    row.push(n.text);
                    row.push(n.rect.x);
                    row.push(n.rect.y);
                    row.push(n.rect.w);
                    row.push(n.rect.h);
                    for (const k of STYLE_KEYS) row.push(n.style[k]);
                    rows.push(row.map(esc).join(','));
                }
                downloadText(rows.join('\n'), 'text/csv;charset=utf-8', `${base}_design_snapshot_${scope}_${timestamp}.csv`);
                showStatus('デザインスナップショット(CSV)を出力しました', 'success');
            } else {
                const json = JSON.stringify(snapshot, null, 2);
                downloadText(json, 'application/json;charset=utf-8', `${base}_design_snapshot_${scope}_${timestamp}.json`);
                showStatus('デザインスナップショット(JSON)を出力しました', 'success');
            }

            closeModal('designExportModal');
        };
        
        // モーダルを閉じる
        window.closeModal = function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }
        
        // ステータスメッセージを表示
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 3000);
        }
        
        // ファイルをダウンロード（グローバル関数として明示的に定義）
        window.downloadFile = function downloadFile() {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            const content = editor.value;
            if (!content || content.trim() === '') {
                showStatus('ダウンロードする内容がありません', 'error');
                return;
            }
            
            try {
                const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // ファイル名を取得（現在のファイル名またはデフォルト名）
                // グローバル変数から取得
                const currentFilename = window.editorFilename || '';
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                const downloadFilename = currentFilename && currentFilename.trim() !== '' ? 
                    currentFilename.replace(/\.html?$/i, '') + '_edited.html' : 
                    'html_edited_' + timestamp + '.html';
                
                a.download = downloadFilename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showStatus('ファイルをダウンロードしました: ' + downloadFilename, 'success');
            } catch (error) {
                showStatus('ダウンロードエラー: ' + error.message, 'error');
            }
        };
        
        // プレビューをHTMLファイルとしてダウンロード
        window.downloadPreview = function downloadPreview() {
            const editor = getEditor();
            if (!editor) {
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            
            const content = editor.value;
            if (!content || content.trim() === '') {
                showStatus('ダウンロードする内容がありません', 'error');
                return;
            }
            
            try {
                // HTMLファイルとしてダウンロード
                const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // ファイル名を取得（現在のファイル名またはデフォルト名）
                const currentFilename = window.editorFilename || '';
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                const downloadFilename = currentFilename && currentFilename.trim() !== '' ? 
                    currentFilename.replace(/\.html?$/i, '') + '_preview.html' : 
                    'html_preview_' + timestamp + '.html';
                
                a.download = downloadFilename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showStatus('プレビューをHTMLファイルとしてダウンロードしました: ' + downloadFilename, 'success');
            } catch (error) {
                showStatus('ダウンロードエラー: ' + error.message, 'error');
            }
        };
        
        // アップロードモーダルを表示
        window.showUploadModal = function showUploadModal() {
            document.getElementById('uploadModal').style.display = 'block';
        };
        
        // 設定を読み込んでプレースホルダーを更新
        async function loadConfigAndUpdatePlaceholders() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                if (data.success) {
                    const defaultDir = data.default_html_directory;
                    const isCloud = data.is_cloud;
                    const dirInfo = data.directory_info;
                    
                    // ディレクトリ情報をコンソールに表示（デバッグ用）
                    if (dirInfo) {
                        console.log('📂 HTML_DIRECTORY 情報:', {
                            path: dirInfo.path,
                            exists: dirInfo.exists,
                            file_count: dirInfo.file_count,
                            files: dirInfo.files
                        });
                        
                        if (dirInfo.exists) {
                            console.log(`✅ ディレクトリが存在します: ${dirInfo.path}`);
                            console.log(`📁 ファイル数: ${dirInfo.file_count}件`);
                            if (dirInfo.files && dirInfo.files.length > 0) {
                                console.log('📄 ファイル一覧:');
                                dirInfo.files.forEach(file => {
                                    const sizeKB = (file.size / 1024).toFixed(2);
                                    const modified = new Date(file.modified * 1000).toLocaleString('ja-JP');
                                    console.log(`  - ${file.name} (${sizeKB} KB, 更新: ${modified})`);
                                });
                            } else {
                                console.log('⚠️ ディレクトリは存在しますが、ファイルが見つかりませんでした');
                            }
                        } else {
                            console.warn(`❌ ディレクトリが存在しません: ${dirInfo.path}`);
                            if (dirInfo.error) {
                                console.error('エラー:', dirInfo.error);
                            }
                        }
                    }
                    
                    // プレースホルダーを更新
                    const placeholders = {
                        'fileListDir': defaultDir ? `例: ${defaultDir} または空欄でアップロードフォルダ` : '例: C:\\html または空欄でアップロードフォルダ',
                        'comparisonDir': isCloud ? '例: /data/html または /tmp/html (Linux形式の絶対パス)' : '例: C:\\html または C:/html (絶対パスを指定)',
                        'diffAnalysisDir': isCloud ? '例: /data/html または /tmp/html (Linux形式の絶対パス)' : '例: C:\\html または C:/html (絶対パスを指定)',
                        'templateMergeDir': defaultDir ? `例: ${defaultDir} または空欄でアップロードフォルダ` : '例: C:\\html または空欄でアップロードフォルダ',
                        'quickComparisonDir': defaultDir || (isCloud ? '/data/html' : 'C:\\html')
                    };
                    
                    // 各入力フィールドのプレースホルダーを更新
                    Object.keys(placeholders).forEach(id => {
                        const element = document.getElementById(id);
                        if (element) {
                            element.placeholder = placeholders[id];
                        }
                    });
                }
            } catch (error) {
                console.error('設定の読み込みエラー:', error);
            }
        }
        
        // ファイル一覧を表示
        window.showFileList = function showFileList() {
            document.getElementById('fileListModal').style.display = 'block';
            // ディレクトリが指定されていない場合はアップロードフォルダを表示
            const dirInput = document.getElementById('fileListDir');
            if (!dirInput || !dirInput.value.trim()) {
                loadUploadedFiles();
            } else {
                loadDirectoryFiles();
            }
        };
        
        // アップロードフォルダのファイルを読み込み
        async function loadUploadedFiles() {
            try {
                const response = await fetch('/files');
                const data = await response.json();
                if (data.success) {
                    // ファイルタイプを追加
                    const filesWithType = data.files.map(file => ({
                        ...file,
                        type: file.name.match(/\.html?$/i) ? 'html' : 'other'
                    }));
                    displayFileList(filesWithType, 'アップロードフォルダ');
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                    document.getElementById('fileListContent').innerHTML = `<p style="text-align: center; padding: 40px; color: #ef4444;">エラー: ${data.error}</p>`;
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
                document.getElementById('fileListContent').innerHTML = `<p style="text-align: center; padding: 40px; color: #ef4444;">エラー: ${error.message}</p>`;
            }
        }
        
        // 指定ディレクトリのファイルを読み込み
        window.loadDirectoryFiles = async function loadDirectoryFiles() {
            const dirInput = document.getElementById('fileListDir');
            let dirPath = dirInput ? dirInput.value.trim() : '';
            
            const fileListContent = document.getElementById('fileListContent');
            fileListContent.innerHTML = '<p style="text-align: center; padding: 40px; color: #4a5568;">ファイルを読み込み中...</p>';
            
            try {
                let response;
                if (!dirPath) {
                    // ディレクトリが空の場合は、まず環境変数を確認
                    const configResponse = await fetch('/api/config');
                    const configData = await configResponse.json();
                    if (configData.success && configData.default_html_directory) {
                        // 環境変数が設定されている場合はそれを使用
                        dirPath = configData.default_html_directory;
                    } else {
                        // 環境変数もない場合はアップロードフォルダを読み込み
                        response = await fetch('/files');
                        const data = await response.json();
                        if (data.success) {
                            const filesWithType = data.files.map(file => ({
                                ...file,
                                type: file.name.match(/\.html?$/i) ? 'html' : 'other'
                            }));
                            displayFileList(filesWithType, 'アップロードフォルダ');
                        }
                        return;
                    }
                }
                
                if (dirPath) {
                    // Windowsパスの正規化
                    let normalizedPath = dirPath.replace(/\\\\/g, '\\');
                    if (normalizedPath.match(/^[a-zA-Z]:/)) {
                        // ドライブレターを大文字に正規化
                        normalizedPath = normalizedPath[0].toUpperCase() + normalizedPath.substring(1).replace(/\//g, '\\');
                    }
                    
                    response = await fetch('/api/list-directory-files', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ directory: normalizedPath })
                    });
                }
                
                const data = await response.json();
                if (data.success) {
                    displayFileList(data.files, dirPath);
                } else {
                    fileListContent.innerHTML = `
                        <div style="color: #ef4444; text-align: center; padding: 20px;">
                            <p style="margin: 0 0 10px 0; font-weight: 600;">エラー: ${data.error || 'ファイルの読み込みに失敗しました'}</p>
                            ${data.error && data.error.includes('ディレクトリ') ? `
                                <p style="margin: 0; font-size: 12px; color: #718096;">
                                    パスの例: C:\\html または C:/html<br>
                                    絶対パスを指定してください
                                </p>
                            ` : ''}
                        </div>
                    `;
                    showStatus(data.error || 'ファイルの読み込みに失敗しました', 'error');
                }
            } catch (error) {
                fileListContent.innerHTML = `<p style="text-align: center; padding: 40px; color: #ef4444;">エラー: ${error.message}</p>`;
                showStatus('ファイルの読み込み中にエラーが発生しました', 'error');
                console.error('Error loading directory files:', error);
            }
        };
        
        // ファイル一覧を表示（共通関数）
        let allFileListFiles = [];
        function displayFileList(files, directoryName) {
            allFileListFiles = files;
            filterFileList();
        }
        
        // ファイル一覧をフィルタリング
        window.filterFileList = function filterFileList() {
            const fileListContent = document.getElementById('fileListContent');
            const searchInput = document.getElementById('fileListSearch');
            const identifierSearchInput = document.getElementById('fileListIdentifierSearch');
            const typeFilter = document.getElementById('fileListTypeFilter');
            
            const searchTerm = (searchInput ? searchInput.value.toLowerCase() : '').trim();
            const identifierTerm = (identifierSearchInput ? identifierSearchInput.value.toLowerCase() : '').trim();
            const typeFilterValue = typeFilter ? typeFilter.value : 'all';
            
            // フィルタリング
            const filteredFiles = allFileListFiles.filter(file => {
                // ファイル名での検索
                const matchesSearch = !searchTerm || file.name.toLowerCase().includes(searchTerm);
                
                // ファイルタイプでのフィルタ
                const fileType = file.type || (file.name.match(/\.(html?|css)$/i) ? 
                    (file.name.match(/\.html?$/i) ? 'html' : 'css') : 'other');
                const matchesType = typeFilterValue === 'all' || fileType === typeFilterValue;
                
                // 識別子での検索（HTMLファイルのみ）
                let matchesIdentifier = true;
                if (identifierTerm && fileType === 'html' && file.identifiers) {
                    const identifiers = file.identifiers;
                    const allIdentifiers = [
                        ...(identifiers.ids || []),
                        ...(identifiers.classes || []),
                        ...(identifiers.data_attrs || [])
                    ].map(id => id.toLowerCase());
                    matchesIdentifier = allIdentifiers.some(id => id.includes(identifierTerm));
                }
                
                return matchesSearch && matchesType && matchesIdentifier;
            });
            
            if (filteredFiles.length === 0) {
                fileListContent.innerHTML = '<p style="text-align: center; padding: 40px; color: #718096;">該当するファイルがありません</p>';
                return;
            }
            
            let html = '<div style="max-height: 500px; overflow-y: auto;">';
            html += '<table style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr style="background: #f7fafc; border-bottom: 2px solid #e2e8f0; position: sticky; top: 0; z-index: 10;">';
            html += '<th style="padding: 12px; text-align: left; font-weight: 600; color: #2d3748;">ファイル名</th>';
            html += '<th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748;">タイプ</th>';
            html += '<th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748;">識別子</th>';
            html += '<th style="padding: 12px; text-align: right; font-weight: 600; color: #2d3748;">サイズ</th>';
            html += '<th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748;">操作</th>';
            html += '</tr></thead>';
            html += '<tbody>';
            
            filteredFiles.forEach(file => {
                const fileType = file.type || (file.name.match(/\.(html?|css)$/i) ? 
                    (file.name.match(/\.html?$/i) ? 'html' : 'css') : 'other');
                const typeBadgeColor = fileType === 'html' ? '#667eea' : fileType === 'css' ? '#10b981' : '#6c757d';
                const typeBadgeText = fileType === 'html' ? 'HTML' : fileType === 'css' ? 'CSS' : 'OTHER';
                const fileSize = file.size || 0;
                const sizeText = fileSize >= 1024 * 1024 ? 
                    `${(fileSize / (1024 * 1024)).toFixed(2)} MB` : 
                    fileSize >= 1024 ? 
                    `${(fileSize / 1024).toFixed(2)} KB` : 
                    `${fileSize} bytes`;
                
                // 識別子情報を表示
                let identifierInfo = '';
                if (fileType === 'html' && file.identifiers) {
                    const ids = file.identifiers.ids || [];
                    const classes = file.identifiers.classes || [];
                    const dataAttrs = file.identifiers.data_attrs || [];
                    const totalCount = ids.length + classes.length + dataAttrs.length;
                    
                    if (totalCount > 0) {
                        const idsDisplay = ids.slice(0, 3).map(id => escapeHtml(id)).join(', ') + (ids.length > 3 ? '...' : '');
                        const classesDisplay = classes.slice(0, 3).map(cls => escapeHtml(cls)).join(', ') + (classes.length > 3 ? '...' : '');
                        const dataAttrsDisplay = dataAttrs.slice(0, 2).map(attr => escapeHtml(attr)).join(', ') + (dataAttrs.length > 2 ? '...' : '');
                        identifierInfo = `
                            <div style="display: flex; flex-direction: column; gap: 4px; font-size: 10px;">
                                ${ids.length > 0 ? `<div><span style="color: #667eea; font-weight: 600;">ID:</span> <span style="color: #4a5568;">${idsDisplay}</span></div>` : ''}
                                ${classes.length > 0 ? `<div><span style="color: #10b981; font-weight: 600;">Class:</span> <span style="color: #4a5568;">${classesDisplay}</span></div>` : ''}
                                ${dataAttrs.length > 0 ? `<div><span style="color: #f59e0b; font-weight: 600;">Data:</span> <span style="color: #4a5568;">${dataAttrsDisplay}</span></div>` : ''}
                                <div style="color: #718096; margin-top: 2px;">合計: ${totalCount}個</div>
                            </div>
                        `;
                    } else {
                        identifierInfo = '<span style="color: #cbd5e0; font-size: 11px;">識別子なし</span>';
                    }
                } else {
                    identifierInfo = '<span style="color: #cbd5e0; font-size: 11px;">-</span>';
                }
                
                html += `<tr style="border-bottom: 1px solid #e2e8f0; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background=''">`;
                html += `<td style="padding: 12px; font-weight: 500; color: #2d3748;">${escapeHtml(file.name)}</td>`;
                html += `<td style="padding: 12px; text-align: center;">`;
                html += `<span style="padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: rgba(${fileType === 'html' ? '102, 126, 234' : fileType === 'css' ? '16, 185, 129' : '108, 117, 125'}, 0.1); color: ${typeBadgeColor};">${typeBadgeText}</span>`;
                html += `</td>`;
                html += `<td style="padding: 12px; text-align: left; max-width: 300px; font-size: 11px;">${identifierInfo}</td>`;
                html += `<td style="padding: 12px; text-align: right; color: #718096; font-size: 12px;">${sizeText}</td>`;
                html += `<td style="padding: 12px; text-align: center;">`;
                if (file.path) {
                    // ディレクトリから読み込んだファイル
                    html += `<button class="btn btn-primary" style="padding: 6px 15px; font-size: 12px; margin-right: 5px;" onclick="loadFileFromPath('${escapeHtml(file.path)}', '${escapeHtml(file.name)}')" title="ファイルを開く">開く</button>`;
                } else {
                    // アップロードフォルダのファイル
                    html += `<button class="btn btn-primary" style="padding: 6px 15px; font-size: 12px; margin-right: 5px;" onclick="loadFile('${escapeHtml(file.name)}')" title="ファイルを開く">開く</button>`;
                    html += `<button class="btn btn-danger" style="padding: 6px 15px; font-size: 12px;" onclick="deleteFile('${escapeHtml(file.name)}')" title="ファイルを削除">削除</button>`;
                }
                html += `</td></tr>`;
            });
            
            html += '</tbody></table>';
            html += `<div style="margin-top: 15px; padding: 10px; background: #f0f4f8; border-radius: 5px; font-size: 12px; color: #4a5568;">`;
            html += `表示中: ${filteredFiles.length}件 / 合計: ${allFileListFiles.length}件`;
            html += `</div>`;
            html += '</div>';
            
            fileListContent.innerHTML = html;
        };
        
        // パスからファイルを読み込む
        window.loadFileFromPath = async function loadFileFromPath(filePath, fileName) {
            try {
                const response = await fetch(`/api/load-file-content?path=${encodeURIComponent(filePath)}`);
                const data = await response.json();
                if (data.success && data.content) {
                    const editor = getEditor();
                    if (editor) {
                        editor.value = data.content;
                        updatePreview();
                        closeModal('fileListModal');
                        showStatus(`${fileName} を読み込みました`, 'success');
                    } else {
                        showStatus('エディタが見つかりません', 'error');
                    }
                } else {
                    showStatus('エラー: ' + (data.error || 'ファイルの読み込みに失敗しました'), 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // ファイルを読み込む（グローバル関数として明示的に定義）
        window.loadFile = async function loadFile(filename) {
            const editor = getEditor();
            if (!editor) {
                console.error('エディタ要素が見つかりません');
                showStatus('エディタが見つかりません', 'error');
                return;
            }
            try {
                const response = await fetch(`/load/${encodeURIComponent(filename)}`);
                const data = await response.json();
                if (data.success) {
                    editor.value = data.content;
                    updatePreview();
                    closeModal('fileListModal');
                    location.reload();
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        };
        
        // ファイルを削除
        async function deleteFile(filename) {
            if (!confirm(`ファイル "${filename}" を削除しますか？`)) {
                return;
            }
            try {
                const response = await fetch(`/delete/${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    showFileList();
                    showStatus('ファイルを削除しました', 'success');
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        }
        
        // ファイル名を更新
        function updateFileName() {
            const fileInput = document.getElementById('fileInput');
            const fileNameDiv = document.getElementById('fileName');
            if (fileInput.files.length > 0) {
                fileNameDiv.textContent = '選択されたファイル: ' + fileInput.files[0].name;
                fileNameDiv.style.display = 'block';
            } else {
                fileNameDiv.style.display = 'none';
            }
        }
        
        // ドラッグ&ドロップ対応
        const uploadModal = document.getElementById('uploadModal');
        const fileInput = document.getElementById('fileInput');
        const dropZone = fileInput.parentElement;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#4299e1';
                dropZone.style.background = '#ebf8ff';
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#cbd5e0';
                dropZone.style.background = '#f7fafc';
            }, false);
        });
        
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
                updateFileName();
            }
        }, false);
        
        // アップロードフォームの処理
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData();
            const fileInput = document.getElementById('fileInput');
            if (fileInput.files.length === 0) {
                showStatus('ファイルを選択してください', 'error');
                return;
            }
            
            const file = fileInput.files[0];
            if (!file.name.toLowerCase().endsWith('.html') && !file.name.toLowerCase().endsWith('.htm')) {
                showStatus('HTMLファイル（.html, .htm）のみアップロード可能です', 'error');
                return;
            }
            
            formData.append('file', file);
            
            try {
                showStatus('アップロード中...', 'success');
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    showStatus('ファイルをアップロードしました！編集を開始できます。', 'success');
                    closeModal('uploadModal');
                    setTimeout(() => {
                        location.reload();
                    }, 500);
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        });
        
        // モーダルの外側をクリックで閉じる
        window.onclick = function(event) {
            const modals = ['structureModal', 'searchModal', 'designExportModal', 'templateMergeModal', 'diffAnalysisModal', 'uploadModal', 'fileListModal'];
            modals.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (event.target == modal) {
                    modal.style.display = 'none';
                }
            });
        }
        
        // HTML構文チェック
        window.validateHTML = async function validateHTML() {
            await validateHTMLContent(true);
        }
        
        // HTML構文チェック（内部関数）
        async function validateHTMLContent(showPanel = false) {
            const editor = getEditor();
            if (!editor) {
                return;
            }
            const content = editor.value;
            if (!content.trim()) {
                return;
            }
            
            try {
                const response = await fetch('/validate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ content: content })
                });
                
                const data = await response.json();
                if (data.success) {
                    displayErrors(data.errors, showPanel);
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        }
        
        // エラーを表示
        function displayErrors(errors, showPanel = false) {
            const errorPanel = document.getElementById('errorPanel');
            const errorList = document.getElementById('errorList');
            
            if (errors.length === 0) {
                errorPanel.style.display = 'none';
                showStatus('構文エラーは見つかりませんでした！', 'success');
                return;
            }
            
            let html = '';
            errors.forEach((error, index) => {
                const typeClass = error.type === 'error' ? 'error' : 'warning';
                const typeIcon = error.type === 'error' ? '❌' : '⚠️';
                const typeLabel = error.type === 'error' ? 'エラー' : '警告';
                
                html += `<div class="error-item ${typeClass}">`;
                html += `<div class="error-item-header">${typeIcon} ${typeLabel}</div>`;
                html += `<div class="error-item-message">${escapeHtml(error.message)}</div>`;
                html += `<div class="error-item-location">`;
                html += `行: ${error.line}`;
                if (error.column > 0) {
                    html += `, 列: ${error.column}`;
                }
                html += ` <span class="error-item-link" onclick="goToLine(${error.line}, ${error.column})">[移動]</span>`;
                html += `</div>`;
                html += `</div>`;
            });
            
            errorList.innerHTML = html;
            if (showPanel || errors.length > 0) {
                errorPanel.style.display = 'block';
            }
        }
        
        // HTMLエスケープ
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // 指定した行に移動
        function goToLine(line, column) {
            const editor = getEditor();
            if (!editor) {
                return;
            }
            const lines = editor.value.split('\n');
            let position = 0;
            
            // 指定された行までの文字数を計算
            for (let i = 0; i < line - 1 && i < lines.length; i++) {
                position += lines[i].length + 1; // +1は改行文字
            }
            
            // 列を追加
            if (column > 0 && line <= lines.length) {
                position += Math.min(column, lines[line - 1].length);
            }
            
            // カーソルを移動
            editor.focus();
            editor.setSelectionRange(position, position);
            editor.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        
        // Ctrl+Sで保存
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                if (document.getElementById('saveBtn').disabled === false) {
                    saveFile();
                }
            }
            
            // 上下矢印キーで検索結果を移動
            // 検索結果が存在し、検索ボックス以外にフォーカスがある場合のみ処理
            if (window.searchMatches && window.searchMatches.length > 0) {
                const searchBox = document.getElementById('searchBox');
                const activeElement = document.activeElement;
                
                // 検索ボックスにフォーカスがない場合のみ処理
                if (activeElement !== searchBox) {
                    if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        highlightNext();
                    } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        highlightPrevious();
                    }
                }
            }
        });
        // 画面比較機能
        let comparisonFiles = [];
        let comparisonMode = false;
        let selectedScreenIndex = -1;
        
        window.showScreenComparison = function showScreenComparison() {
            const modal = document.getElementById('screenComparisonModal');
            const quickSection = document.getElementById('screenComparisonQuickSection');
            
            if (modal) {
                modal.style.display = 'block';
                // クイック操作セクションを表示
                if (quickSection) {
                    quickSection.style.display = 'block';
                }
                
                // 保存された状態を復元
                const restored = restoreScreenComparisonState();
                
                // リモコン盤のディレクトリパスをモーダルに同期
                const quickDir = document.getElementById('quickComparisonDir');
                const modalDir = document.getElementById('comparisonDir');
                if (quickDir && modalDir) {
                    if (quickDir.value && !restored) {
                        modalDir.value = quickDir.value;
                    }
                }
                
                // 既存のファイルリストがあれば表示
                if (comparisonFiles.length > 0) {
                    displayComparisonFiles();
                    updateQuickFileCount();
                }
            } else {
                showStatus('画面比較モーダルが見つかりません', 'error');
            }
        };
        
        // リモコン盤からのクイック操作関数
        window.quickLoadComparisonFiles = async function quickLoadComparisonFiles() {
            const quickDir = document.getElementById('quickComparisonDir');
            const modalDir = document.getElementById('comparisonDir');
            
            if (!quickDir || !quickDir.value.trim()) {
                showStatus('ディレクトリパスを入力してください', 'error');
                return;
            }
            
            // モーダルが開いていない場合は開く
            const modal = document.getElementById('screenComparisonModal');
            if (modal && modal.style.display !== 'block') {
                showScreenComparison();
            }
            
            // モーダルのディレクトリ入力に値を設定
            if (modalDir) {
                modalDir.value = quickDir.value.trim();
            }
            
            // ファイル読み込みを実行
            await loadComparisonFiles();
            updateQuickFileCount();
        };
        
        window.quickUpdateLayout = function quickUpdateLayout() {
            const quickLayout = document.getElementById('quickLayout');
            const modalLayout = document.getElementById('comparisonLayout');
            
            if (quickLayout && modalLayout) {
                modalLayout.value = quickLayout.value;
                updateComparisonLayout();
            }
        };
        
        window.quickToggleComparisonMode = function quickToggleComparisonMode() {
            toggleComparisonMode();
            // ボタンの状態を更新
            const quickBtn = document.getElementById('quickComparisonModeBtn');
            const modalBtn = document.getElementById('comparisonModeBtn');
            if (quickBtn && modalBtn) {
                quickBtn.textContent = modalBtn.textContent;
                quickBtn.className = modalBtn.className;
            }
        };
        
        window.quickExportReport = function quickExportReport() {
            exportComparisonReport();
        };
        
        function updateQuickFileCount() {
            const fileCountSpan = document.getElementById('quickFileCount');
            const selectedCountSpan = document.getElementById('quickSelectedCount');
            
            if (fileCountSpan) {
                fileCountSpan.textContent = `ファイル: ${comparisonFiles.length}件`;
            }
            
            if (selectedCountSpan) {
                const selectedCount = comparisonFiles.filter((f, i) => {
                    const checkbox = document.getElementById(`file_${i}`);
                    return checkbox && checkbox.checked;
                }).length;
                selectedCountSpan.textContent = `選択: ${selectedCount}件`;
            }
        }
        
        // ファイル選択状態が変更されたときにカウントを更新（後で定義される関数をラップ）
        
        window.loadComparisonFiles = async function loadComparisonFiles() {
            let dirPath = document.getElementById('comparisonDir').value.trim();
            if (!dirPath) {
                // 空欄の場合はアップロードフォルダを使用
                dirPath = '';
            }
            
            // Windowsパスの正規化
            // バックスラッシュのエスケープを処理（c:\\html -> c:\html）
            dirPath = dirPath.replace(/\\\\/g, '\\');
            
            // スラッシュをバックスラッシュに変換（Windowsの場合）
            if (dirPath.match(/^[a-zA-Z]:/)) {
                // Windowsのドライブレターがある場合
                // ドライブレターを大文字に正規化
                dirPath = dirPath[0].toUpperCase() + dirPath.substring(1).replace(/\//g, '\\');
            }
            
            const fileListDiv = document.getElementById('comparisonFileList');
            fileListDiv.innerHTML = '<p style="color: #4a5568; text-align: center;">ファイルを読み込み中...</p>';
            
            try {
                const response = await fetch('/api/load-comparison-files', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ directory: dirPath })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // HTMLファイルを優先し、関連するCSSも含める
                    const allFiles = data.files || [];
                    const htmlFiles = allFiles.filter(f => f.type === 'html').slice(0, 27);
                    const cssFiles = allFiles.filter(f => f.type === 'css');
                    
                    // HTMLファイルとその関連CSSを統合
                    comparisonFiles = [];
                    const addedCss = new Set();
                    
                    htmlFiles.forEach(htmlFile => {
                        comparisonFiles.push(htmlFile);
                        // 関連するCSSファイルも追加
                        if (htmlFile.relatedFiles) {
                            htmlFile.relatedFiles.forEach(cssPath => {
                                if (!addedCss.has(cssPath)) {
                                    const cssFile = cssFiles.find(f => f.path === cssPath);
                                    if (cssFile) {
                                        comparisonFiles.push(cssFile);
                                        addedCss.add(cssPath);
                                    }
                                }
                            });
                        }
                    });
                    
                    // 関連付けられていないCSSファイルも追加（オプション）
                    cssFiles.forEach(cssFile => {
                        if (!addedCss.has(cssFile.path) && comparisonFiles.length < 50) {
                            comparisonFiles.push(cssFile);
                        }
                    });
                    
                    displayComparisonFiles();
                    renderComparisonScreens();
                    updateQuickFileCount();
                    // 状態を保存
                    saveScreenComparisonState();
                    const cssCount = comparisonFiles.filter(f => f.type === 'css').length;
                    showStatus(`${comparisonFiles.length}個のファイルを読み込みました（HTML: ${htmlFiles.length}, CSS: ${cssCount}）`, 'success');
                } else {
                    const errorMsg = data.error || 'ファイルの読み込みに失敗しました';
                    fileListDiv.innerHTML = `
                        <div style="color: #ef4444; text-align: center; padding: 10px;">
                            <p style="margin: 0 0 10px 0; font-weight: 600;">エラー: ${errorMsg}</p>
                            <p style="margin: 0; font-size: 11px; color: #718096;">
                                パスの例: C:\\html または C:/html<br>
                                絶対パスを指定してください
                            </p>
                        </div>
                    `;
                    showStatus(errorMsg, 'error');
                }
            } catch (error) {
                fileListDiv.innerHTML = `<p style="color: #ef4444; text-align: center;">エラー: ${error.message}</p>`;
                showStatus('ファイルの読み込み中にエラーが発生しました', 'error');
                console.error('Error loading comparison files:', error);
            }
        };
        
        // ファイル検索・フィルタ用の変数
        let filteredComparisonFiles = [];
        
        function displayComparisonFiles() {
            const fileListDiv = document.getElementById('comparisonFileList');
            if (comparisonFiles.length === 0) {
                fileListDiv.innerHTML = '<p style="color: #718096; font-size: 12px; margin: 0; text-align: center;">ファイルがありません</p>';
                return;
            }
            
            // フィルタリング
            applyFileFilters();
        }
        
        function applyFileFilters() {
            const fileListDiv = document.getElementById('comparisonFileList');
            const searchInput = document.getElementById('fileSearchInput');
            const typeFilter = document.getElementById('fileTypeFilter');
            
            const searchTerm = (searchInput ? searchInput.value.toLowerCase() : '').trim();
            const typeFilterValue = typeFilter ? typeFilter.value : 'all';
            
            // フィルタリング
            filteredComparisonFiles = comparisonFiles.filter((file, index) => {
                const matchesSearch = !searchTerm || file.name.toLowerCase().includes(searchTerm);
                const matchesType = typeFilterValue === 'all' || file.type === typeFilterValue;
                return matchesSearch && matchesType;
            });
            
            // 表示
            if (filteredComparisonFiles.length === 0) {
                fileListDiv.innerHTML = '<p style="color: #718096; font-size: 12px; margin: 0; text-align: center; padding: 20px;">該当するファイルがありません</p>';
                return;
            }
            
            const fileListHTML = filteredComparisonFiles.map((file, filteredIndex) => {
                // 元のインデックスを取得
                const originalIndex = comparisonFiles.findIndex(f => f === file);
                const fileType = file.type || 'other';
                const typeBadgeColor = fileType === 'html' ? '#667eea' : fileType === 'css' ? '#10b981' : '#6c757d';
                const typeBadgeText = fileType === 'html' ? 'HTML' : fileType === 'css' ? 'CSS' : 'OTHER';
                const relatedFilesCount = file.relatedFiles && file.relatedFiles.length > 0 ? ` (関連: ${file.relatedFiles.length})` : '';
                const checkbox = document.getElementById(`file_${originalIndex}`);
                const isChecked = checkbox ? checkbox.checked : true;
                
                return `
                <div class="comparison-file-item" data-index="${originalIndex}" style="display: flex; align-items: center; gap: 10px; padding: 8px; background: white; border-radius: 4px; margin-bottom: 5px; border: 1px solid #e2e8f0; transition: all 0.2s;">
                    <input type="checkbox" id="file_${originalIndex}" ${isChecked ? 'checked' : ''} onchange="toggleComparisonFile(${originalIndex})" style="cursor: pointer;">
                    <label for="file_${originalIndex}" style="flex: 1; cursor: pointer; font-size: 12px; color: #2d3748; display: flex; align-items: center; gap: 8px;">
                        <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</span>
                        <span style="padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; background: rgba(${fileType === 'html' ? '102, 126, 234' : fileType === 'css' ? '16, 185, 129' : '108, 117, 125'}, 0.1); color: ${typeBadgeColor}; flex-shrink: 0;">${typeBadgeText}</span>
                        ${relatedFilesCount ? `<span style="font-size: 10px; color: #718096; flex-shrink: 0;">${relatedFilesCount}</span>` : ''}
                    </label>
                    <span style="font-size: 11px; color: #718096; flex-shrink: 0; min-width: 60px; text-align: right;">${(file.size / 1024).toFixed(1)} KB</span>
                    <button onclick="event.stopPropagation(); removeComparisonFile(${originalIndex})" style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; flex-shrink: 0;" title="ファイルを削除">削除</button>
                </div>
            `;
            }).join('');
            
            const selectedCount = comparisonFiles.filter((f, i) => {
                const checkbox = document.getElementById(`file_${i}`);
                return checkbox && checkbox.checked;
            }).length;
            
            fileListDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <strong style="font-size: 13px; color: #2d3748;">読み込み済み: ${comparisonFiles.length}件</strong>
                        ${searchTerm || typeFilterValue !== 'all' ? `<span style="font-size: 12px; color: #667eea;">表示中: ${filteredComparisonFiles.length}件</span>` : ''}
                        <span style="font-size: 12px; color: #10b981;">選択中: ${selectedCount}件</span>
                    </div>
                    <div style="display: flex; gap: 5px;">
                        <button onclick="selectAllComparisonFiles(true)" style="background: #667eea; color: white; border: none; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">すべて選択</button>
                        <button onclick="selectAllComparisonFiles(false)" style="background: #e2e8f0; color: #4a5568; border: none; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">すべて解除</button>
                    </div>
                </div>
                <div style="max-height: 150px; overflow-y: auto;">
                    ${fileListHTML}
                </div>
            `;
        }
        
        window.filterComparisonFiles = function filterComparisonFiles() {
            applyFileFilters();
        };
        
        window.sortComparisonFiles = function sortComparisonFiles() {
            const sortOption = document.getElementById('fileSortOption').value;
            
            comparisonFiles.sort((a, b) => {
                switch (sortOption) {
                    case 'name':
                        return a.name.localeCompare(b.name);
                    case 'size':
                        return (b.size || 0) - (a.size || 0);
                    case 'type':
                        const typeOrder = { 'html': 1, 'css': 2, 'other': 3 };
                        return (typeOrder[a.type] || 99) - (typeOrder[b.type] || 99);
                    default:
                        return 0;
                }
            });
            
            displayComparisonFiles();
        };
        
        function renderComparisonScreens() {
            const grid = document.getElementById('comparisonGrid');
            if (!grid) return;
            
            const activeFiles = comparisonFiles.filter((f, i) => {
                const checkbox = document.getElementById(`file_${i}`);
                return !checkbox || checkbox.checked;
            });
            
            if (activeFiles.length === 0) {
                grid.innerHTML = '<p style="text-align: center; color: #718096; padding: 40px;">表示するファイルを選択してください</p>';
                return;
            }
            
            updateComparisonLayout();
            
            grid.innerHTML = activeFiles.map((file, index) => {
                const actualIndex = comparisonFiles.findIndex(f => f === file);
                const fileType = file.type || 'other';
                const typeBadgeColor = fileType === 'html' ? 'rgba(255, 255, 255, 0.3)' : fileType === 'css' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(108, 117, 125, 0.3)';
                const typeBadgeText = fileType === 'html' ? 'HTML' : fileType === 'css' ? 'CSS' : 'OTHER';
                const relatedFilesInfo = file.relatedFiles && file.relatedFiles.length > 0 ? `<span style="font-size: 10px; color: rgba(255, 255, 255, 0.8); margin-left: 8px;">関連: ${file.relatedFiles.length}</span>` : '';
                return `
                    <div class="comparison-screen" data-index="${actualIndex}" onclick="selectComparisonScreen(${actualIndex})">
                        <div class="comparison-screen-header">
                            <div style="display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden;">
                                <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</span>
                                <span style="padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; background: ${typeBadgeColor}; color: white; border: 1px solid rgba(255, 255, 255, 0.5); flex-shrink: 0;">${typeBadgeText}</span>
                                ${relatedFilesInfo}
                            </div>
                            <div class="screen-actions">
                                <button onclick="event.stopPropagation(); editComparisonScreen(${actualIndex})" title="編集">✏️</button>
                                <button onclick="event.stopPropagation(); downloadComparisonScreen(${actualIndex})" title="ダウンロード">⬇️</button>
                                <button onclick="event.stopPropagation(); analyzeComparisonScreen(${actualIndex})" title="分析">📊</button>
                            </div>
                        </div>
                        <div class="comparison-screen-preview" id="preview_${actualIndex}">
                            <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 300px; color: #718096;">
                                <div style="text-align: center;">
                                    <div class="spinner" style="width: 40px; height: 40px; border: 4px solid #e2e8f0; border-top-color: #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                                    <p>読み込み中...</p>
                                </div>
                            </div>
                        </div>
                        <div class="comparison-screen-info">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <span>${(file.size / 1024).toFixed(1)} KB</span>
                                ${file.relatedFiles && file.relatedFiles.length > 0 ? `<span style="padding: 2px 6px; background: rgba(99, 102, 241, 0.1); color: #667eea; border-radius: 4px; font-size: 10px; font-weight: 600;">関連: ${file.relatedFiles.length}</span>` : ''}
                            </div>
                            <span class="diff-badge same" id="diff_badge_${actualIndex}">比較中...</span>
                        </div>
                        <div class="comparison-mode-overlay"></div>
                    </div>
                `;
            }).join('');
            
            // 各ファイルの内容を読み込んでプレビューに表示
            activeFiles.forEach((file, idx) => {
                const actualIndex = comparisonFiles.findIndex(f => f === file);
                loadComparisonScreenContent(actualIndex);
            });
            
            // 比較分析を実行
            if (activeFiles.length > 1) {
                performComparisonAnalysis();
            }
        }
        
        async function loadComparisonScreenContent(index) {
            const file = comparisonFiles[index];
            if (!file) return;
            
            const previewDiv = document.getElementById(`preview_${index}`);
            if (!previewDiv) return;
            
            try {
                const response = await fetch(`/api/load-file-content?path=${encodeURIComponent(file.path)}`);
                const data = await response.json();
                
                if (data.success && data.content) {
                    const fileType = file.type || 'other';
                    
                    if (fileType === 'css') {
                        // CSSファイルの場合はコードビューで表示（シンタックスハイライト付き）
                        const highlightedCss = highlightCSS(data.content);
                        previewDiv.innerHTML = `<pre>${highlightedCss}</pre>`;
                    } else if (fileType === 'html') {
                        // HTMLファイルの場合はiframeで表示
                        const blob = new Blob([data.content], { type: 'text/html' });
                        const url = URL.createObjectURL(blob);
                        previewDiv.innerHTML = `<iframe sandbox="allow-same-origin allow-scripts allow-forms allow-popups" style="width: 100%; height: 100%; border: none;" src="${url}" title="HTMLプレビュー"></iframe>`;
                    } else {
                        // その他のファイルタイプ
                        previewDiv.innerHTML = `
                            <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 300px; color: #718096;">
                                <p>プレビューを表示できません（${fileType}ファイル）</p>
                            </div>
                        `;
                    }
                } else {
                    previewDiv.innerHTML = `
                        <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 300px; color: #ef4444;">
                            <p>⚠️ ファイルの読み込みに失敗しました</p>
                        </div>
                    `;
                }
            } catch (error) {
                previewDiv.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 300px; color: #ef4444;">
                        <p>⚠️ エラー: ${error.message || 'ファイルの読み込み中にエラーが発生しました'}</p>
                    </div>
                `;
                console.error(`Error loading screen content for ${file.name}:`, error);
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function highlightCSS(css) {
            // 簡易的なCSSシンタックスハイライト
            if (!css) return '';
            
            return escapeHtml(css)
                // @ルールをハイライト
                .replace(/(@[a-z-]+)/gi, '<span style="color: #f78c6c;">$1</span>')
                // セレクタをハイライト（{の前、ただしコメントや空行は除外）
                .replace(/([^{}@\n]+)(?=\{)/g, function(match) {
                    const trimmed = match.trim();
                    if (trimmed.startsWith('/*') || trimmed.startsWith('*') || !trimmed) return match;
                    return '<span style="color: #82aaff;">' + match + '</span>';
                })
                // プロパティ名をハイライト
                .replace(/([a-z-]+)(?=:)/gi, '<span style="color: #c792ea;">$1</span>')
                // プロパティ値をハイライト
                .replace(/(:\s*)([^;]+)(?=;)/g, '$1<span style="color: #c3e88d;">$2</span>')
                // コメントをハイライト
                .replace(/(\/\*[\s\S]*?\*\/)/g, '<span style="color: #546e7a; font-style: italic;">$1</span>');
        }
        
        async function performComparisonAnalysis() {
            const activeFiles = comparisonFiles.filter((f, i) => {
                const checkbox = document.getElementById(`file_${i}`);
                return !checkbox || checkbox.checked;
            });
            
            if (activeFiles.length < 2) return;
            
            try {
                const response = await fetch('/api/compare-screens', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        files: activeFiles.map(f => f.path)
                    })
                });
                
                const data = await response.json();
                
                if (data.success && data.comparison) {
                    // 比較結果を表示（HTMLとCSSの差分を含む）
                    activeFiles.forEach((file, idx) => {
                        const actualIndex = comparisonFiles.findIndex(f => f === file);
                        const badge = document.getElementById(`diff_badge_${actualIndex}`);
                        if (badge) {
                            const comparison = data.comparison[file.path];
                            if (comparison) {
                                const totalDiff = comparison.differences || 0;
                                const htmlDiff = comparison.htmlDifferences || 0;
                                const cssDiff = comparison.cssDifferences || 0;
                                
                                if (totalDiff === 0) {
                                    badge.textContent = '同一';
                                    badge.className = 'diff-badge same';
                                } else {
                                    let diffText = `${totalDiff}箇所の差異`;
                                    if (htmlDiff > 0 || cssDiff > 0) {
                                        const parts = [];
                                        if (htmlDiff > 0) parts.push(`HTML: ${htmlDiff}`);
                                        if (cssDiff > 0) parts.push(`CSS: ${cssDiff}`);
                                        diffText += ` (${parts.join(', ')})`;
                                    }
                                    badge.textContent = diffText;
                                    badge.className = 'diff-badge different';
                                    badge.title = `HTML差分: ${htmlDiff}箇所, CSS差分: ${cssDiff}箇所`;
                                }
                            } else {
                                badge.textContent = '比較不可';
                                badge.className = 'diff-badge error';
                            }
                        }
                    });
                }
            } catch (error) {
                console.error('Error performing comparison analysis:', error);
            }
        }
        
        window.toggleComparisonFile = function toggleComparisonFile(index) {
            renderComparisonScreens();
            updateQuickFileCount();
            // 状態を保存
            saveScreenComparisonState();
        };
        
        window.removeComparisonFile = function removeComparisonFile(index) {
            comparisonFiles.splice(index, 1);
            displayComparisonFiles();
            renderComparisonScreens();
        };
        
        window.selectAllComparisonFiles = function selectAllComparisonFiles(select) {
            comparisonFiles.forEach((file, index) => {
                const checkbox = document.getElementById(`file_${index}`);
                if (checkbox) {
                    checkbox.checked = select;
                }
            });
            renderComparisonScreens();
            updateQuickFileCount();
            // 状態を保存
            saveScreenComparisonState();
        };
        
        window.selectComparisonScreen = function selectComparisonScreen(index) {
            // すべてのスクリーンの選択状態を解除
            document.querySelectorAll('.comparison-screen').forEach(screen => {
                screen.classList.remove('selected');
            });
            
            // 選択したスクリーンをハイライト
            const screen = document.querySelector(`.comparison-screen[data-index="${index}"]`);
            if (screen) {
                screen.classList.add('selected');
                selectedScreenIndex = index;
            }
        };
        
        window.editComparisonScreen = function editComparisonScreen(index) {
            const file = comparisonFiles[index];
            if (!file) return;
            
            // 新しいタブでエディタを開く
            window.open(`/?file=${encodeURIComponent(file.path)}`, '_blank');
        };
        
        window.downloadComparisonScreen = async function downloadComparisonScreen(index) {
            const file = comparisonFiles[index];
            if (!file) return;
            
            try {
                const response = await fetch(`/api/load-file-content?path=${encodeURIComponent(file.path)}`);
                const data = await response.json();
                
                if (data.success && data.content) {
                    const blob = new Blob([data.content], { type: 'text/html' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = file.name;
                    a.click();
                    URL.revokeObjectURL(url);
                    showStatus(`${file.name}をダウンロードしました`, 'success');
                }
            } catch (error) {
                showStatus('ダウンロードに失敗しました', 'error');
                console.error('Error downloading file:', error);
            }
        };
        
        window.analyzeComparisonScreen = function analyzeComparisonScreen(index) {
            const file = comparisonFiles[index];
            if (!file) return;
            
            // 分析結果を表示（既存のデザイン出力機能を使用）
            showStatus(`${file.name}の分析を開始します...`, 'info');
            // ここで分析機能を呼び出す
        };
        
        // 画面比較の状態保存イベントリスナーを設定
        function setupScreenComparisonStateSaving() {
            // ディレクトリパスの変更を監視
            const comparisonDir = document.getElementById('comparisonDir');
            const quickComparisonDir = document.getElementById('quickComparisonDir');
            if (comparisonDir) {
                comparisonDir.addEventListener('change', saveScreenComparisonState);
                comparisonDir.addEventListener('blur', saveScreenComparisonState);
            }
            if (quickComparisonDir) {
                quickComparisonDir.addEventListener('change', saveScreenComparisonState);
                quickComparisonDir.addEventListener('blur', saveScreenComparisonState);
            }
            
            // レイアウト変更を監視
            const layoutSelect = document.getElementById('comparisonLayout');
            if (layoutSelect) {
                layoutSelect.addEventListener('change', saveScreenComparisonState);
            }
        }
        
        window.updateComparisonLayout = function updateComparisonLayout() {
            // 状態を保存
            saveScreenComparisonState();
            const grid = document.getElementById('comparisonGrid');
            const layout = document.getElementById('comparisonLayout').value;
            
            if (grid) {
                grid.className = 'comparison-grid';
                if (layout === 'grid') {
                    grid.classList.add('grid-layout');
                } else if (layout === 'horizontal') {
                    grid.classList.add('horizontal-layout');
                } else if (layout === 'vertical') {
                    grid.classList.add('vertical-layout');
                }
            }
        };
        
        // ==================== 大学データ管理機能 ====================
        let currentUniversityId = null;
        let currentPageTitleId = null;
        
        window.showUniversityDataManagement = async function showUniversityDataManagement() {
            const modal = document.getElementById('universityDataModal');
            if (modal) {
                modal.style.display = 'block';
                await loadUniversities();
                await loadPageTitles();
            }
        };
        
        async function loadUniversities() {
            try {
                const response = await fetch('/api/universities');
                const data = await response.json();
                
                if (data.success) {
                    const listDiv = document.getElementById('universityList');
                    if (data.universities.length === 0) {
                        listDiv.innerHTML = '<p style="color: #718096; font-size: 12px; margin: 0;">大学が登録されていません</p>';
                    } else {
                        listDiv.innerHTML = data.universities.map(uni => `
                            <div style="padding: 8px; margin-bottom: 5px; background: ${currentUniversityId === uni.id ? '#e0e7ff' : 'white'}; border-radius: 4px; cursor: pointer; border: 1px solid #e2e8f0;" 
                                 onclick="selectUniversity(${uni.id}, '${uni.code}', '${uni.name}')">
                                <div style="font-weight: 600; font-size: 13px;">${uni.name}</div>
                                <div style="font-size: 11px; color: #718096;">コード: ${uni.code}</div>
                            </div>
                        `).join('');
                    }
                }
            } catch (error) {
                console.error('大学一覧の読み込みエラー:', error);
            }
        }
        
        async function loadPageTitles() {
            try {
                const response = await fetch('/api/page-titles');
                const data = await response.json();
                
                if (data.success) {
                    const select = document.getElementById('pageTitleSelect');
                    select.innerHTML = '<option value="">-- ページを選択 --</option>' +
                        data.titles.map(title => 
                            `<option value="${title.id}">${title.title}</option>`
                        ).join('');
                }
            } catch (error) {
                console.error('ページタイトル一覧の読み込みエラー:', error);
            }
        }
        
        window.selectUniversity = function selectUniversity(id, code, name) {
            currentUniversityId = id;
            loadUniversities();
            loadUniversityPageData();
        };
        
        window.addUniversity = async function addUniversity() {
            const code = document.getElementById('newUniversityCode').value.trim();
            const name = document.getElementById('newUniversityName').value.trim();
            
            if (!code || !name) {
                showStatus('大学コードと名前を入力してください', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/universities', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code, name})
                });
                
                const data = await response.json();
                if (data.success) {
                    document.getElementById('newUniversityCode').value = '';
                    document.getElementById('newUniversityName').value = '';
                    await loadUniversities();
                    showStatus('大学を登録しました', 'success');
                } else {
                    showStatus(data.error || '登録に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('登録に失敗しました', 'error');
                console.error(error);
            }
        };
        
        window.loadUniversityPageData = async function loadUniversityPageData() {
            if (!currentUniversityId) {
                showStatus('大学を選択してください', 'error');
                return;
            }
            
            const pageTitleId = document.getElementById('pageTitleSelect').value;
            if (!pageTitleId) {
                document.getElementById('pageContentEditor').value = '';
                document.getElementById('pageMetadataEditor').value = '{}';
                return;
            }
            
            currentPageTitleId = parseInt(pageTitleId);
            
            try {
                const response = await fetch(`/api/university/${currentUniversityId}/page/${currentPageTitleId}`);
                const data = await response.json();
                
                if (data.success && data.page) {
                    document.getElementById('pageContentEditor').value = data.page.content || '';
                    document.getElementById('pageMetadataEditor').value = data.page.metadata || '{}';
                } else {
                    document.getElementById('pageContentEditor').value = '';
                    document.getElementById('pageMetadataEditor').value = '{}';
                }
            } catch (error) {
                console.error('ページデータの読み込みエラー:', error);
            }
        };
        
        window.saveUniversityPageData = async function saveUniversityPageData() {
            if (!currentUniversityId || !currentPageTitleId) {
                showStatus('大学とページを選択してください', 'error');
                return;
            }
            
            const content = document.getElementById('pageContentEditor').value;
            let metadata = {};
            try {
                metadata = JSON.parse(document.getElementById('pageMetadataEditor').value);
            } catch (e) {
                showStatus('メタデータのJSON形式が正しくありません', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/university/${currentUniversityId}/page/${currentPageTitleId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({content, metadata})
                });
                
                const data = await response.json();
                if (data.success) {
                    showStatus('ページデータを保存しました', 'success');
                } else {
                    showStatus(data.error || '保存に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('保存に失敗しました', 'error');
                console.error(error);
            }
        };
        
        window.loadUniversityConfig = async function loadUniversityConfig() {
            if (!currentUniversityId) {
                showStatus('大学を選択してください', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/university/${currentUniversityId}/config`);
                const data = await response.json();
                
                if (data.success) {
                    const config = data.config || {layout: {}, display_order: [], items: {}};
                    
                    // JSONエディタに設定
                    document.getElementById('universityConfigEditor').value = JSON.stringify(config, null, 2);
                    
                    // 表示順序エディタに設定
                    document.getElementById('displayOrderEditor').value = JSON.stringify(config.display_order || [], null, 2);
                    
                    // 項目一覧を表示
                    renderConfigItems(config.items || {});
                    
                    // モーダルを表示
                    document.getElementById('universityConfigModal').style.display = 'block';
                    switchConfigTab('items'); // デフォルトで項目属性タブを表示
                }
            } catch (error) {
                console.error('設定の読み込みエラー:', error);
            }
        };
        
        window.switchConfigTab = function switchConfigTab(tab) {
            // すべてのタブコンテンツを非表示
            document.getElementById('configTabItemsContent').style.display = 'none';
            document.getElementById('configTabLayoutContent').style.display = 'none';
            document.getElementById('configTabRawContent').style.display = 'none';
            
            // すべてのタブボタンのスタイルをリセット
            document.getElementById('configTabItems').style.background = '#e2e8f0';
            document.getElementById('configTabItems').style.color = '#4a5568';
            document.getElementById('configTabLayout').style.background = '#e2e8f0';
            document.getElementById('configTabLayout').style.color = '#4a5568';
            document.getElementById('configTabRaw').style.background = '#e2e8f0';
            document.getElementById('configTabRaw').style.color = '#4a5568';
            
            // 選択されたタブを表示
            if (tab === 'items') {
                document.getElementById('configTabItemsContent').style.display = 'block';
                document.getElementById('configTabItems').style.background = '#667eea';
                document.getElementById('configTabItems').style.color = 'white';
            } else if (tab === 'layout') {
                document.getElementById('configTabLayoutContent').style.display = 'block';
                document.getElementById('configTabLayout').style.background = '#667eea';
                document.getElementById('configTabLayout').style.color = 'white';
            } else if (tab === 'raw') {
                document.getElementById('configTabRawContent').style.display = 'block';
                document.getElementById('configTabRaw').style.background = '#667eea';
                document.getElementById('configTabRaw').style.color = 'white';
            }
        };
        
        function renderConfigItems(items) {
            const listDiv = document.getElementById('configItemsList');
            if (!items || Object.keys(items).length === 0) {
                listDiv.innerHTML = '<p style="color: #718096; font-size: 12px; margin: 0;">項目がありません</p>';
                return;
            }
            
            listDiv.innerHTML = Object.entries(items).map(([itemId, itemAttrs]) => `
                <div style="padding: 12px; margin-bottom: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 5px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="font-weight: 600; font-size: 13px;">${itemId}</div>
                        <button class="btn" onclick="editConfigItem('${itemId}')" style="font-size: 11px; padding: 4px 8px; background: #667eea; color: white; border: none; border-radius: 3px; cursor: pointer;">編集</button>
                    </div>
                    <div style="font-size: 11px; color: #718096;">
                        ${itemAttrs.visible === false ? '❌ 非表示' : '✅ 表示'} | 
                        ${itemAttrs.order !== undefined ? `順序: ${itemAttrs.order}` : ''} |
                        ${itemAttrs.id ? `ID: ${itemAttrs.id}` : ''} |
                        ${itemAttrs.class ? `Class: ${itemAttrs.class}` : ''}
                    </div>
                </div>
            `).join('');
        }
        
        window.addConfigItem = function addConfigItem() {
            const itemId = document.getElementById('newItemId').value.trim();
            if (!itemId) {
                showStatus('項目IDを入力してください', 'error');
                return;
            }
            
            editConfigItem(itemId, true);
        };
        
        window.editConfigItem = function editConfigItem(itemId, isNew = false) {
            // 現在の設定を取得
            let config = {};
            try {
                const configText = document.getElementById('universityConfigEditor').value;
                if (configText) {
                    config = JSON.parse(configText);
                }
            } catch (e) {
                config = {items: {}};
            }
            
            if (!config.items) {
                config.items = {};
            }
            
            const itemAttrs = config.items[itemId] || {};
            
            // 編集用のモーダルを表示（簡易版）
            const newAttrs = {
                id: prompt('要素ID（空欄可）:', itemAttrs.id || ''),
                class: prompt('要素クラス（空欄可）:', itemAttrs.class || ''),
                visible: confirm('表示しますか？') ? true : false,
                order: parseInt(prompt('表示順序（数値）:', itemAttrs.order || '0') || '0'),
                styles: itemAttrs.styles || {}
            };
            
            // スタイルの編集
            const stylesText = prompt('CSSスタイル（JSON形式、例: {"margin-top": "20px"}）:', JSON.stringify(itemAttrs.styles || {}, null, 2));
            if (stylesText) {
                try {
                    newAttrs.styles = JSON.parse(stylesText);
                } catch (e) {
                    showStatus('スタイルのJSON形式が正しくありません', 'error');
                    return;
                }
            }
            
            config.items[itemId] = newAttrs;
            
            // 設定を更新
            document.getElementById('universityConfigEditor').value = JSON.stringify(config, null, 2);
            renderConfigItems(config.items);
            
            if (isNew) {
                document.getElementById('newItemId').value = '';
            }
            
            showStatus('項目を追加しました', 'success');
        };
        
        window.saveUniversityConfig = async function saveUniversityConfig() {
            if (!currentUniversityId) {
                showStatus('大学を選択してください', 'error');
                return;
            }
            
            let config = {};
            
            // 現在表示中のタブから設定を取得
            const activeTab = document.getElementById('configTabItemsContent').style.display !== 'none' ? 'items' :
                             document.getElementById('configTabLayoutContent').style.display !== 'none' ? 'layout' : 'raw';
            
            if (activeTab === 'raw') {
                // JSON編集タブから直接取得
                try {
                    config = JSON.parse(document.getElementById('universityConfigEditor').value);
                } catch (e) {
                    showStatus('JSON形式が正しくありません', 'error');
                    return;
                }
            } else {
                // 項目属性タブまたはレイアウトタブから取得
                try {
                    // 既存の設定を読み込む
                    const configText = document.getElementById('universityConfigEditor').value;
                    if (configText) {
                        config = JSON.parse(configText);
                    }
                } catch (e) {
                    config = {layout: {}, display_order: [], items: {}};
                }
                
                // 表示順序を更新
                if (activeTab === 'layout') {
                    try {
                        config.display_order = JSON.parse(document.getElementById('displayOrderEditor').value);
                    } catch (e) {
                        showStatus('表示順序のJSON形式が正しくありません', 'error');
                        return;
                    }
                }
            }
            
            try {
                const response = await fetch(`/api/university/${currentUniversityId}/config`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config})
                });
                
                const data = await response.json();
                if (data.success) {
                    closeUniversityConfigModal();
                    showStatus('設定を保存しました', 'success');
                } else {
                    showStatus(data.error || '保存に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('保存に失敗しました', 'error');
                console.error(error);
            }
        };
        
        window.closeUniversityConfigModal = function closeUniversityConfigModal() {
            document.getElementById('universityConfigModal').style.display = 'none';
        };
        
        // YAML設定ファイルからページを一括生成
        window.generatePagesFromYAML = async function generatePagesFromYAML() {
            const universityCodesInput = document.getElementById('yamlUniversityCodes');
            const outputDirectoryInput = document.getElementById('yamlOutputDirectory');
            const resultDiv = document.getElementById('yamlGenerationResult');
            const resultContent = document.getElementById('yamlGenerationResultContent');
            
            // 大学コードを取得（カンマ区切り）
            let university_codes = [];
            if (universityCodesInput && universityCodesInput.value.trim()) {
                university_codes = universityCodesInput.value.split(',').map(code => code.trim()).filter(code => code);
            }
            
            const output_directory = outputDirectoryInput && outputDirectoryInput.value.trim() ? outputDirectoryInput.value.trim() : '';
            
            try {
                showStatus('ページ生成中...', 'success');
                resultDiv.style.display = 'block';
                resultContent.innerHTML = '<p>生成中...</p>';
                
                const response = await fetch('/api/generate-pages-from-yaml', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        university_codes: university_codes,
                        output_directory: output_directory
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    let html = `<div style="color: #10b981; font-weight: 600; margin-bottom: 10px;">✅ 生成完了</div>`;
                    html += `<div style="margin-bottom: 10px;">`;
                    html += `<p><strong>対象大学数:</strong> ${data.universities_count}大学</p>`;
                    html += `<p><strong>生成ページ数:</strong> ${data.total_pages}ページ</p>`;
                    html += `<p><strong>成功:</strong> ${data.success_count}ページ</p>`;
                    if (data.failed_count > 0) {
                        html += `<p style="color: #ef4444;"><strong>失敗:</strong> ${data.failed_count}ページ</p>`;
                    }
                    html += `<p><strong>出力ディレクトリ:</strong> ${data.output_directory}</p>`;
                    html += `</div>`;
                    
                    if (data.generated_files && data.generated_files.length > 0) {
                        html += `<div style="max-height: 300px; overflow-y: auto; margin-top: 15px; padding: 10px; background: #f8fafc; border-radius: 5px;">`;
                        html += `<strong>生成されたファイル:</strong><ul style="margin-top: 10px; padding-left: 20px;">`;
                        data.generated_files.slice(0, 20).forEach(file => {
                            html += `<li style="margin-bottom: 5px; font-size: 11px;">${file.university_code} - ${file.page_title} (${file.file_name})</li>`;
                        });
                        if (data.generated_files.length > 20) {
                            html += `<li style="color: #718096;">... 他 ${data.generated_files.length - 20} ファイル</li>`;
                        }
                        html += `</ul></div>`;
                    }
                    
                    resultContent.innerHTML = html;
                    showStatus(data.message || 'ページ生成が完了しました', 'success');
                    
                    // 出力ディレクトリを保存
                    window.yamlOutputDirectory = data.output_directory;
                } else {
                    resultContent.innerHTML = `<div style="color: #ef4444;">❌ エラー: ${data.error}</div>`;
                    showStatus('ページ生成に失敗しました: ' + data.error, 'error');
                }
            } catch (error) {
                resultContent.innerHTML = `<div style="color: #ef4444;">❌ エラー: ${error.message}</div>`;
                showStatus('ページ生成に失敗しました', 'error');
                console.error(error);
            }
        };
        
        // 生成済みページをダウンロード
        window.downloadGeneratedPagesFromYAML = async function downloadGeneratedPagesFromYAML() {
            const outputDirectoryInput = document.getElementById('yamlOutputDirectory');
            const output_directory = (outputDirectoryInput && outputDirectoryInput.value.trim()) ? outputDirectoryInput.value.trim() : (window.yamlOutputDirectory || '');
            
            if (!output_directory) {
                showStatus('出力ディレクトリが指定されていません', 'error');
                return;
            }
            
            try {
                showStatus('ZIPファイルを作成中...', 'success');
                
                const response = await fetch('/api/generate-pages-from-yaml-download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        output_directory: output_directory
                    })
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `university_pages_${new Date().toISOString().slice(0, 10)}.zip`;
                    a.click();
                    URL.revokeObjectURL(url);
                    showStatus('ZIPファイルをダウンロードしました', 'success');
                } else {
                    const data = await response.json();
                    showStatus('ダウンロードに失敗しました: ' + (data.error || '不明なエラー'), 'error');
                }
            } catch (error) {
                showStatus('ダウンロードに失敗しました', 'error');
                console.error(error);
            }
        };
        
        window.generateUniversityPage = async function generateUniversityPage() {
            if (!currentUniversityId || !currentPageTitleId) {
                showStatus('大学とページを選択してください', 'error');
                return;
            }
            
            // 共通テンプレートを取得（統合済みテンプレートがあれば使用）
            const template = window.mergedTemplate || '<html><head><title>Generated Page</title></head><body><div id="content"></div></body></html>';
            
            try {
                const response = await fetch('/api/generate-university-page', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        university_id: currentUniversityId,
                        page_title_id: currentPageTitleId,
                        template: template
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    // 生成されたHTMLをエディタに表示
                    const editor = getEditor();
                    if (editor) {
                        editor.value = data.html;
                        updatePreview();
                        showStatus('ページを生成しました', 'success');
                    } else {
                        // エディタが開いていない場合はダウンロード
                        const blob = new Blob([data.html], { type: 'text/html' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `university_${currentUniversityId}_page_${currentPageTitleId}.html`;
                        a.click();
                        URL.revokeObjectURL(url);
                        showStatus('ページを生成してダウンロードしました', 'success');
                    }
                } else {
                    showStatus(data.error || 'ページ生成に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('ページ生成に失敗しました', 'error');
                console.error(error);
            }
        };
        
        window.toggleComparisonMode = function toggleComparisonMode() {
            comparisonMode = !comparisonMode;
            const btn = document.getElementById('comparisonModeBtn');
            const grid = document.getElementById('comparisonGrid');
            
            if (btn) {
                if (comparisonMode) {
                    btn.textContent = '編集モード';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-warning');
                } else {
                    btn.textContent = '比較モード';
                    btn.classList.remove('btn-warning');
                    btn.classList.add('btn-primary');
                }
            }
            
            if (grid) {
                if (comparisonMode) {
                    grid.classList.add('comparison-mode');
                } else {
                    grid.classList.remove('comparison-mode');
                }
            }
        };
        
        window.exportComparisonReport = async function exportComparisonReport() {
            const activeFiles = comparisonFiles.filter((f, i) => {
                const checkbox = document.getElementById(`file_${i}`);
                return !checkbox || checkbox.checked;
            });
            
            if (activeFiles.length < 2) {
                showStatus('比較するには2つ以上のファイルを選択してください', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/export-comparison-report', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        files: activeFiles.map(f => ({ name: f.name, path: f.path }))
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const blob = new Blob([data.report], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'comparison_report.csv';
                    a.click();
                    URL.revokeObjectURL(url);
                    showStatus('比較レポートをダウンロードしました', 'success');
                } else {
                    showStatus('レポートの生成に失敗しました', 'error');
                }
            } catch (error) {
                showStatus('レポートのエクスポート中にエラーが発生しました', 'error');
                console.error('Error exporting comparison report:', error);
            }
        };
        
    </script>
</body>
</html>
"""


def get_session_file_info():
    """
    セッションからファイル情報を取得
    
    Returns:
        dict: セッションに対応するファイル情報
            - 'html_editor': HTMLEditorオブジェクト（未選択時はNone）
            - 'html_file_path': ファイルパス（未選択時はNone）
    """
    # セッションIDを取得（存在しない場合は新規生成）
    session_id = session.get('session_id')
    if not session_id:
        # 新規セッションの場合、16バイトのランダムな16進数文字列を生成
        session_id = secrets.token_hex(16)
        session['session_id'] = session_id
        # セッション用のファイル情報を初期化
        session_files[session_id] = {
            'html_editor': None,
            'html_file_path': None
        }
    # セッションIDに対応するファイル情報を返す（存在しない場合は空の辞書を返す）
    return session_files.get(session_id, {
        'html_editor': None,
        'html_file_path': None
    })


def set_session_file_info(html_editor_obj, file_path):
    """
    セッションにファイル情報を保存
    
    Args:
        html_editor_obj: HTMLEditorオブジェクト
        file_path: ファイルパス（Pathオブジェクトまたは文字列）
    """
    # セッションIDを取得（存在しない場合は新規生成）
    session_id = session.get('session_id')
    if not session_id:
        # 新規セッションの場合、16バイトのランダムな16進数文字列を生成
        session_id = secrets.token_hex(16)
        session['session_id'] = session_id
    
    # セッションIDがsession_filesに存在しない場合は初期化
    if session_id not in session_files:
        session_files[session_id] = {}
    
    # セッションに対応するファイル情報を保存
    session_files[session_id]['html_editor'] = html_editor_obj
    session_files[session_id]['html_file_path'] = file_path


def _find_assets_dir():
    """assetsディレクトリを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    assets_dir = FRONTEND_DIST_DIR / 'assets'
    if assets_dir.exists() and assets_dir.is_dir():
        app.logger.info(f"assetsディレクトリを見つけました（FRONTEND_DIST_DIR）: {assets_dir}")
        return assets_dir
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        assets_dir = dist_dir / 'assets'
        if assets_dir.exists() and assets_dir.is_dir():
            app.logger.info(f"assetsディレクトリを見つけました（代替パス）: {assets_dir}")
            return assets_dir
    
    # 見つからない場合はログを出力
    app.logger.error(f"assetsディレクトリが見つかりません。試したパス:")
    app.logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'assets'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        app.logger.error(f"  - {dist_dir / 'assets'}")
    return None


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """静的アセット（JS、CSSなど）を配信"""
    try:
        # 複数のパスからassetsディレクトリを検索
        assets_dir = _find_assets_dir()
        if assets_dir:
            return send_from_directory(str(assets_dir), filename)
        else:
            # デフォルトのパスを試す
            app.logger.warning(f"assetsディレクトリが見つかりません。デフォルトパスを試します: {FRONTEND_DIST_DIR / 'assets'}")
            return send_from_directory(str(FRONTEND_DIST_DIR / 'assets'), filename)
    except Exception as e:
        app.logger.error(f"静的アセット配信エラー: {e}, filename: {filename}")
        # 404エラーを返す代わりに、空のレスポンスを返す（ブラウザのエラーを減らすため）
        return '', 404


@app.route('/favicon.ico')
def favicon():
    """faviconを返す（404エラーを防ぐため）"""
    try:
        # 複数のパスからfaviconを検索
        for dist_dir in _ALTERNATIVE_PATHS:
            favicon_path = dist_dir / 'favicon.ico'
            if favicon_path.exists():
                return send_file(str(favicon_path))
        
        # 見つからない場合は空のICOファイルを返す
        return send_file(io.BytesIO(b''), mimetype='image/x-icon')
    except Exception:
        return send_file(io.BytesIO(b''), mimetype='image/x-icon')


def _find_index_html():
    """index.htmlを複数のパスから検索"""
    # まずFRONTEND_DIST_DIRをチェック
    index_path = FRONTEND_DIST_DIR / 'index.html'
    if index_path.exists():
        app.logger.info(f"index.htmlを見つけました（FRONTEND_DIST_DIR）: {index_path}")
        return index_path
    
    # 次に代替パスを試す
    for dist_dir in _ALTERNATIVE_PATHS:
        index_path = dist_dir / 'index.html'
        if index_path.exists():
            app.logger.info(f"index.htmlを見つけました（代替パス）: {index_path}")
            return index_path
    
    # 見つからない場合はログを出力
    app.logger.error(f"index.htmlが見つかりません。試したパス:")
    app.logger.error(f"  - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'index.html'}")
    for dist_dir in _ALTERNATIVE_PATHS:
        app.logger.error(f"  - {dist_dir / 'index.html'}")
    return None


def _serve_index_html():
    """index.htmlを返す共通関数"""
    try:
        # 詳細なログを出力（Railway環境でのデバッグ用）
        msg = f"=== index.html配信開始 ===\n現在の作業ディレクトリ: {os.getcwd()}\nスクリプトのディレクトリ: {Path(__file__).parent}\nFRONTEND_DIST_DIR: {FRONTEND_DIST_DIR}\nFRONTEND_DIST_DIR 存在確認: {FRONTEND_DIST_DIR.exists()}"
        app.logger.info(msg)
        print(msg, flush=True)  # printも追加して確実にログを出力
        
        # 複数のパスからindex.htmlを検索
        index_path = _find_index_html()
        
        if index_path:
            msg = f"index.htmlを配信します: {index_path}"
            app.logger.info(msg)
            print(msg, flush=True)
            return send_file(str(index_path))
        else:
            # ビルドファイルが存在しない場合は、エラーメッセージを返す
            app.logger.error(f"Reactビルドファイルが見つかりません。試したパス: {[str(p / 'index.html') for p in _ALTERNATIVE_PATHS]}")
            error_html = f"""
            <!DOCTYPE html>
            <html lang="ja">
            <head>
                <meta charset="UTF-8">
                <title>ビルドファイルが見つかりません</title>
                <style>
                    body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                    .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>ビルドファイルが見つかりません</h1>
                    <p>frontend/dist/index.html が存在しません。ビルドを実行してください。</p>
                    <p><strong>作業ディレクトリ:</strong> {os.getcwd()}</p>
                    <p><strong>スクリプトのディレクトリ:</strong> {Path(__file__).parent}</p>
                    <p><strong>試したパス:</strong></p>
                    <ul>
                        {''.join([f'<li>{str(p / "index.html")}</li>' for p in _ALTERNATIVE_PATHS])}
                    </ul>
                </div>
            </body>
            </html>
            """
            return error_html, 500
    except Exception as e:
        error_details = traceback.format_exc()
        app.logger.error(f"index.html配信エラー: {error_details}")
        error_html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <title>エラー</title>
            <style>
                body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
                .error {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                pre {{ background: #f0f0f0; padding: 15px; border-radius: 4px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>エラーが発生しました</h1>
                <p><strong>エラーメッセージ:</strong> {str(e)}</p>
                <h2>詳細:</h2>
                <pre>{error_details}</pre>
            </div>
        </body>
        </html>
        """
        return error_html, 500


@app.route('/')
def index():
    """メインページ - Reactアプリケーションを配信"""
    msg = "=== ルートパス (/) へのリクエスト ==="
    app.logger.info(msg)
    print(msg, flush=True)  # printも追加して確実にログを出力
    try:
        result = _serve_index_html()
        msg = f"index() の戻り値の型: {type(result)}"
        app.logger.info(msg)
        print(msg, flush=True)
        return result
    except Exception as e:
        error_msg = f"index() でエラーが発生: {e}"
        app.logger.error(error_msg)
        print(error_msg, flush=True)
        import traceback
        tb = traceback.format_exc()
        app.logger.error(tb)
        print(tb, flush=True)
        raise


@app.errorhandler(404)
def handle_404(e):
    """404エラーハンドラー - APIルート以外はindex.htmlを返す（SPAルーティング）"""
    path = request.path
    app.logger.warning(f"=== 404エラー発生 ===")
    app.logger.warning(f"Path: {path}")
    app.logger.warning(f"Method: {request.method}")
    app.logger.warning(f"URL: {request.url}")
    app.logger.warning(f"Error: {e}")
    
    # 静的アセットの場合は404を返す（既にserve_assetsで処理されているが、念のため）
    if path.startswith('/assets/'):
        app.logger.warning(f"静的アセットが見つかりません: {path}")
        return '', 404
    
    # APIルートの場合は404を返す
    if path.startswith('/api/') or path.startswith('/save') or path.startswith('/upload') or \
       path.startswith('/files') or path.startswith('/search') or path.startswith('/structure') or \
       path.startswith('/validate') or path.startswith('/download') or path.startswith('/content') or \
       path.startswith('/reload') or path.startswith('/load/') or path.startswith('/delete/') or \
       path.startswith('/diff-analysis') or path.startswith('/gcd-template') or \
       path.startswith('/generate-university-pages') or path.startswith('/download-university-pages') or \
       path.startswith('/template-merge'):
        return jsonify({'error': 'Not found'}), 404
    
    # それ以外はReactアプリを返す（SPAルーティング）
    app.logger.info(f"404エラーをキャッチ: {path} -> index.htmlを返します")
    return _serve_index_html()


@app.route('/save', methods=['POST'])
def save():
    """ファイルを保存"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのみを保存
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        data = request.json
        content = data.get('content', '')
        
        # ファイルに保存
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(html_editor, html_file_path)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/content')
def content():
    """HTMLコンテンツを取得"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのコンテンツのみを返す
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None or not Path(html_file_path).exists():
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reload')
def reload():
    """ファイルを再読み込み"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルのみを再読み込み
        file_info = get_session_file_info()
        html_file_path = file_info.get('html_file_path')
        
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # HTMLEditorを再読み込みして、セッション情報を更新
        html_editor = HTMLEditor(str(html_file_path))
        set_session_file_info(html_editor, html_file_path)
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/structure')
def structure():
    """構造情報を取得"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイルの構造情報のみを返す
        file_info = get_session_file_info()
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return jsonify({'success': False, 'error': 'HTMLエディタが初期化されていません'}), 500
        
        info = html_editor.get_structure_info()
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/search', methods=['POST'])
def search():
    """要素を検索"""
    try:
        # セッションからファイル情報を取得
        # このセッションで選択されているファイル内でのみ検索を実行
        file_info = get_session_file_info()
        html_editor = file_info.get('html_editor')
        
        if html_editor is None:
            return jsonify({'success': False, 'error': 'HTMLエディタが初期化されていません'}), 500
        
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': '検索文字列が空です'})
        
        results = []
        
        # IDで検索
        element = html_editor.find_by_id(query)
        if element:
            results.append({
                'tag': element.name,
                'id': element.get('id', ''),
                'class': ' '.join(element.get('class', [])),
                'type': 'id',
                'text': element.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # クラスで検索
        elements = html_editor.find_by_class(query)
        for elem in elements[:10]:  # 最初の10個のみ
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'class',
                'text': elem.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # タグで検索
        elements = html_editor.find_by_tag(query)
        for elem in elements[:10]:  # 最初の10個のみ
            results.append({
                'tag': elem.name,
                'id': elem.get('id', ''),
                'class': ' '.join(elem.get('class', [])),
                'type': 'tag',
                'text': elem.get_text(strip=True)[:50]  # 最初の50文字
            })
        
        # テキスト内容で検索（部分一致）
        try:
            text_elements = html_editor.find_by_text(query, exact=False)
            for text_node in text_elements[:10]:  # 最初の10個のみ
                # テキストノードの親要素を取得
                parent = text_node.parent if hasattr(text_node, 'parent') else None
                if parent:
                    results.append({
                        'tag': parent.name,
                        'id': parent.get('id', ''),
                        'class': ' '.join(parent.get('class', [])),
                        'type': 'text',
                        'text': text_node.strip()[:50] if isinstance(text_node, str) else str(text_node)[:50]
                    })
        except Exception as e:
            # テキスト検索でエラーが発生した場合は無視
            pass
        
        # HTMLソースコード全体で検索（エディタの内容を検索）
        # クライアント側から送られてくるHTMLソースを検索するため、
        # この検索はクライアント側で行う方が効率的
        # サーバー側では、BeautifulSoupで解析されたHTMLのみを検索
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルをアップロード"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        # ファイル名を安全にする
        filename = secure_filename(file.filename)
        
        # HTMLファイルかチェック
        if not (filename.lower().endswith('.html') or filename.lower().endswith('.htm')):
            return jsonify({'success': False, 'error': 'HTMLファイルのみアップロード可能です'}), 400
        
        # アップロードフォルダに保存
        file_path = UPLOAD_DIR / filename
        file.save(str(file_path))
        
        # セッションにファイル情報を保存
        # このセッションでアップロードしたファイルを選択状態にする
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(html_editor, file_path)
        
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/files')
def list_files():
    """アップロードされたファイル一覧を取得"""
    try:
        files = []
        for file_path in UPLOAD_DIR.glob('*.html'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size
            })
        for file_path in UPLOAD_DIR.glob('*.htm'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size
            })
        
        # ファイル名でソート
        files.sort(key=lambda x: x['name'])
        
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/load/<filename>')
def load_file(filename):
    """ファイルを読み込む"""
    try:
        # ファイル名を安全にする
        safe_filename = secure_filename(filename)
        file_path = UPLOAD_DIR / safe_filename
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # ファイルを読み込む
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # セッションにファイル情報を保存
        # このセッションで読み込んだファイルを選択状態にする
        html_editor = HTMLEditor(str(file_path))
        set_session_file_info(html_editor, file_path)
        
        return jsonify({'success': True, 'content': content, 'filename': safe_filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """ファイルを削除"""
    try:
        # ファイル名を安全にする
        safe_filename = secure_filename(filename)
        file_path = UPLOAD_DIR / safe_filename
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # 現在開いているファイルを削除する場合は、そのセッションのエディタをクリア
        # 削除対象のファイルを開いているすべてのセッションをチェック
        # 複数のセッションが同じファイルを開いている可能性があるため、すべてのセッションを確認
        for session_id, file_info in list(session_files.items()):
            session_file_path = file_info.get('html_file_path')
            if session_file_path and Path(session_file_path) == file_path:
                # 該当セッションのファイル情報をクリア
                session_files[session_id]['html_editor'] = None
                session_files[session_id]['html_file_path'] = None
        
        # ファイルを削除
        file_path.unlink()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/validate', methods=['POST'])
def validate():
    """HTMLの構文を検証"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'リクエストデータがありません'}), 400
        
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'error': 'コンテンツが空です'}), 400
        
        # 一時ファイルに保存して検証
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # HTMLEditorで検証
            temp_editor = HTMLEditor(temp_path)
            errors = temp_editor.validate_html()
            
            return jsonify({'success': True, 'errors': errors})
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_path)
            except:
                pass
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/diff-analysis', methods=['POST', 'OPTIONS'])
def diff_analysis():
    """27校の大学ホームページの差分を検出"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        options = data.get('options', {})
        
        # 空欄またはアップロードフォルダ指定の場合はアップロードフォルダを使用
        use_upload_dir = False
        if not directory or directory == '__upload__':
            # アップロードフォルダを使用
            directory = str(UPLOAD_DIR)
            use_upload_dir = True
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if not use_upload_dir and is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }), 400
        
        # アップロードフォルダの場合はそのまま使用
        if use_upload_dir:
            dir_path = UPLOAD_DIR
        else:
            # Windowsパスの処理: バックスラッシュとスラッシュを正規化
            # c:\\html, c:\html, c:/html を正しく処理
            directory = directory.strip()
            # スラッシュをバックスラッシュに変換（Windowsパスの場合）
            if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
                # Windows絶対パス（例: C:\html, C:/html）
                # ドライブレターを大文字に正規化
                directory = directory[0].upper() + directory[1:].replace('/', '\\')
            else:
                # 相対パスやその他の形式
                directory = directory.replace('\\\\', '\\').replace('/', '\\')
            
            # パスを正規化
            try:
                # Windows絶対パスの場合、Path()で直接処理
                if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                    dir_path = Path(directory)
                else:
                    dir_path = Path(directory).resolve()
            except Exception as e:
                return jsonify({
                    'success': False, 
                    'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
                }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            # より詳細なエラーメッセージ
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if not parent.exists():
                    error_msg += f' (親ディレクトリも存在しません: {parent})'
                else:
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            if not is_cloud:
                error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            else:
                error_msg += f'\nパスの例: /tmp/html または /app/html\nLinux形式の絶対パスを指定してください'
            error_msg += '\n\n💡 ヒント: アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                # ファイル読み込みエラーはスキップ
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}), 400
        
        # 差分を検出
        differences = analyze_differences(parsed_files, options)
        
        # サマリーを生成
        summary = {
            'totalFiles': len(parsed_files),
            'structureDiffs': sum(1 for d in differences if d['type'] == 'structure'),
            'styleDiffs': sum(1 for d in differences if d['type'] == 'style'),
            'contentDiffs': sum(1 for d in differences if d['type'] == 'content'),
            'attributeDiffs': sum(1 for d in differences if d['type'] == 'attribute')
        }
        
        return jsonify({
            'success': True,
            'summary': summary,
            'differences': differences,
            'files': [f['filename'] for f in parsed_files]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def analyze_differences(parsed_files, options):
    """
    HTMLファイル間の差分を分析
    
    処理を最適化するため、以下の制限を設けています:
    - 最大要素数: 1000要素（パフォーマンス向上のため）
    - タイムアウト: 60秒（長時間実行を防ぐため）
    """
    import time
    import signal
    
    differences = []
    
    if len(parsed_files) < 2:
        return differences
    
    # タイムアウト設定（60秒）
    start_time = time.time()
    timeout = 60
    
    # 基準ファイル（最初のファイル）
    base_file = parsed_files[0]
    base_soup = base_file['soup']
    
    # 各要素を比較
    def get_all_elements(soup):
        """すべての要素を取得（最大1000要素に制限）"""
        elements = []
        if soup.body:
            body_elements = soup.body.find_all()
            # 要素数を制限（パフォーマンス向上のため）
            max_elements = 1000
            if len(body_elements) > max_elements:
                # 重要な要素（idやclassを持つ要素）を優先的に取得
                important_elements = [e for e in body_elements if e.get('id') or e.get('class')]
                if len(important_elements) < max_elements:
                    # 重要でない要素も追加
                    other_elements = [e for e in body_elements if not (e.get('id') or e.get('class'))]
                    elements.extend(important_elements)
                    elements.extend(other_elements[:max_elements - len(important_elements)])
                else:
                    elements.extend(important_elements[:max_elements])
            else:
                elements.extend(body_elements)
        if soup.head and options.get('styles', True):
            elements.extend(soup.head.find_all(['style', 'link']))
        return elements
    
    def get_element_signature(elem):
        """要素のシグネチャを取得（比較用）"""
        if not elem or not hasattr(elem, 'name'):
            return None
        
        sig = {
            'tag': elem.name,
            'id': elem.get('id', ''),
            'classes': sorted(elem.get('class', [])) if isinstance(elem.get('class'), list) else [elem.get('class')] if elem.get('class') else []
        }
        return sig
    
    def compare_elements(elem1, elem2):
        """2つの要素を比較"""
        sig1 = get_element_signature(elem1)
        sig2 = get_element_signature(elem2)
        
        if not sig1 or not sig2:
            return False
        
        return sig1['tag'] == sig2['tag'] and sig1['id'] == sig2['id'] and sig1['classes'] == sig2['classes']
    
    # 基準ファイルの要素を取得
    base_elements = get_all_elements(base_soup)
    
    # タイムアウトチェック用のカウンター
    processed_count = 0
    total_elements = len(base_elements)
    
    # 各要素について、他のファイルと比較
    for base_elem in base_elements:
        # タイムアウトチェック
        if time.time() - start_time > timeout:
            differences.append({
                'type': 'system',
                'element': 'timeout',
                'description': f'処理がタイムアウトしました（{timeout}秒）。処理済み: {processed_count}/{total_elements}要素',
                'files': []
            })
            break
        
        processed_count += 1
        
        base_sig = get_element_signature(base_elem)
        if not base_sig:
            continue
        
        # セレクタを生成（最適化: 複雑なセレクタを避ける）
        selector = base_sig['tag']
        if base_sig['id']:
            # IDがある場合はIDセレクタのみを使用（高速）
            selector = f"#{base_sig['id']}"
        elif base_sig['classes']:
            # クラスのみの場合はクラスセレクタを使用
            selector = base_sig['tag'] + '.' + '.'.join(base_sig['classes'][:3])  # 最大3つのクラスのみ使用
        
        # 他のファイルで同じ要素を探す
        matching_files = [base_file['filename']]
        different_files = []
        
        for other_file in parsed_files[1:]:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                break
                
            other_soup = other_file['soup']
            try:
                # セレクタが複雑な場合は、より単純な方法で検索
                if base_sig['id']:
                    found = other_soup.find(id=base_sig['id'])
                elif base_sig['classes']:
                    found = other_soup.find(base_sig['tag'], class_=base_sig['classes'][0] if base_sig['classes'] else None)
                else:
                    found = other_soup.select_one(selector) if selector else None
                if found:
                    matching_files.append(other_file['filename'])
                    
                    # 構造の差分をチェック
                    if options.get('structure', True):
                        if found.name != base_elem.name:
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'structure',
                                'message': f"タグ名が異なります: {found.name} vs {base_elem.name}"
                            })
                    
                    # 属性の差分をチェック
                    if options.get('attributes', True):
                        base_attrs = set(base_elem.attrs.keys())
                        found_attrs = set(found.attrs.keys())
                        
                        # 追加された属性
                        added = found_attrs - base_attrs
                        # 削除された属性
                        removed = base_attrs - found_attrs
                        # 値が異なる属性
                        different = []
                        for attr in base_attrs & found_attrs:
                            if base_elem.get(attr) != found.get(attr):
                                different.append(attr)
                        
                        if added or removed or different:
                            diff_msg = []
                            if added:
                                diff_msg.append(f"追加: {', '.join(added)}")
                            if removed:
                                diff_msg.append(f"削除: {', '.join(removed)}")
                            if different:
                                diff_msg.append(f"変更: {', '.join(different)}")
                            
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'attribute',
                                'message': '; '.join(diff_msg)
                            })
                    
                    # コンテンツの差分をチェック
                    if options.get('content', True):
                        base_text = base_elem.get_text(strip=True)
                        found_text = found.get_text(strip=True)
                        
                        if base_text != found_text:
                            different_files.append({
                                'file': other_file['filename'],
                                'type': 'content',
                                'message': f"テキストが異なります"
                            })
                else:
                    # 要素が見つからない
                    if options.get('structure', True):
                        different_files.append({
                            'file': other_file['filename'],
                            'type': 'structure',
                            'message': '要素が見つかりません'
                        })
            except Exception as e:
                # セレクタが無効な場合はスキップ
                # エラーをログに記録しない（パフォーマンス向上のため）
                pass
        
        # 差分がある場合は記録（最大1000件に制限）
        if different_files and len(differences) < 1000:
            diff_type = different_files[0]['type']
            affected_files = [df['file'] for df in different_files]
            
            differences.append({
                'type': diff_type,
                'element': selector,
                'description': different_files[0]['message'] if different_files else '差分が検出されました',
                'files': affected_files,
                'matchingFiles': matching_files
            })
        
        # 差分が多すぎる場合は早期終了
        if len(differences) >= 1000:
            differences.append({
                'type': 'system',
                'element': 'limit',
                'description': f'差分が多すぎるため、処理を中断しました（最大1000件）。処理済み: {processed_count}/{total_elements}要素',
                'files': []
            })
            break
    
    # スタイルの差分をチェック（タイムアウトチェック付き）
    if options.get('styles', True) and time.time() - start_time < timeout:
        base_styles = []
        if base_soup.head:
            base_styles.extend(base_soup.head.find_all('style'))
            base_styles.extend(base_soup.head.find_all('link', rel='stylesheet'))
        
        for other_file in parsed_files[1:]:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                break
                
            other_soup = other_file['soup']
            other_styles = []
            if other_soup.head:
                other_styles.extend(other_soup.head.find_all('style'))
                other_styles.extend(other_soup.head.find_all('link', rel='stylesheet'))
            
            if len(base_styles) != len(other_styles):
                differences.append({
                    'type': 'style',
                    'element': 'head > style/link',
                    'description': f"スタイルシートの数が異なります: {len(base_styles)} vs {len(other_styles)}",
                    'files': [other_file['filename']]
                })
    
    return differences


@app.route('/gcd-template', methods=['POST'])
def gcd_template():
    """差分を含めて最大公約数的な共通テンプレートを生成"""
    try:
        data = request.json
        directory = data.get('directory', '')
        options = data.get('options', {})
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        # ディレクトリの存在確認
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return jsonify({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}), 404
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                # ファイル読み込みエラーはスキップ
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '比較するには2つ以上のファイルが必要です'}), 400
        
        # 最大公約数テンプレートを生成
        gcd_template, stats = generate_gcd_template(parsed_files, options)
        
        return jsonify({
            'success': True,
            'template': gcd_template,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def generate_gcd_template(parsed_files, options):
    """差分を含めて最大公約数的なテンプレートを生成"""
    if not parsed_files:
        return '', {
            'totalFiles': 0,
            'commonElements': 0,
            'variableElements': 0,
            'mergedElements': 0,
            'variables': []
        }
    
    # 最初のファイルを基準にする
    base_soup = parsed_files[0]['soup'].__class__(str(parsed_files[0]['soup']), 'html.parser')
    base_soup = BeautifulSoup(str(base_soup), 'html.parser')
    
    stats = {
        'totalFiles': len(parsed_files),
        'commonElements': 0,
        'variableElements': 0,
        'mergedElements': 0,
        'variables': []
    }
    
    variable_counter = 1
    
    def get_element_path(elem):
        """要素のパスを取得"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        path = []
        current = elem
        while current and hasattr(current, 'name') and current.name:
            selector = current.name
            if hasattr(current, 'attrs'):
                if 'id' in current.attrs:
                    selector += f"#{current.attrs['id']}"
                elif 'class' in current.attrs:
                    classes = current.attrs['class']
                    if isinstance(classes, list) and classes:
                        selector += '.' + '.'.join(classes[:1])
            path.insert(0, selector)
            current = current.parent if hasattr(current, 'parent') else None
            if current == base_soup or current == base_soup.html or current == base_soup.body:
                break
        return ' > '.join(path)
    
    def merge_element_gcd(base_elem, other_files, path=''):
        """要素を最大公約数的に統合"""
        if not base_elem or not hasattr(base_elem, 'name'):
            return base_elem
        
        current_path = path + ' > ' + base_elem.name if path else base_elem.name
        
        # 他のファイルで同じ要素を探す
        matching_elements = [base_elem]
        base_selector = get_element_selector_for_gcd(base_elem)
        
        for other_data in other_files:
            other_soup = other_data['soup']
            try:
                found = other_soup.select_one(base_selector)
                if found:
                    matching_elements.append(found)
            except Exception:
                pass
        
        # すべてのファイルで見つかった場合
        if len(matching_elements) == len(other_files) + 1:
            # 属性を統合
            if options.get('attributes', True):
                all_attrs = {}
                attr_values = {}
                
                # すべての要素の属性を収集
                for elem in matching_elements:
                    if hasattr(elem, 'attrs'):
                        for key, value in elem.attrs.items():
                            if key not in all_attrs:
                                all_attrs[key] = []
                            if key not in attr_values:
                                attr_values[key] = []
                            
                            if isinstance(value, list):
                                all_attrs[key].extend(value)
                                attr_values[key].append(tuple(sorted(value)))
                            else:
                                all_attrs[key].append(value)
                                attr_values[key].append(value)
                
                # 共通属性を決定
                common_attrs = {}
                variable_attrs = {}
                
                for key, values in attr_values.items():
                    unique_values = set(str(v) for v in values)
                    if len(unique_values) == 1:
                        # すべて同じ値
                        common_attrs[key] = matching_elements[0].attrs[key]
                        stats['commonElements'] += 1
                    else:
                        # 値が異なる場合は変数化
                        var_name = f"VAR_ATTR_{variable_counter}"
                        variable_counter += 1
                        variable_attrs[key] = var_name
                        stats['variableElements'] += 1
                        stats['variables'].append({
                            'name': var_name,
                            'type': 'attribute',
                            'element': current_path,
                            'description': f"属性 '{key}' の値（複数の値が存在: {', '.join(list(unique_values)[:3])}）"
                        })
                        # 最初の値をデフォルトとして使用
                        common_attrs[key] = matching_elements[0].attrs[key]
                
                # 共通属性を設定
                base_elem.attrs.clear()
                base_elem.attrs.update(common_attrs)
                
                # 変数化された属性をコメントとして追加
                if variable_attrs:
                    comment_text = "<!-- "
                    for key, var_name in variable_attrs.items():
                        comment_text += f"{var_name}={key}; "
                    comment_text += "-->"
                    if hasattr(base_elem, 'insert'):
                        base_elem.insert(0, BeautifulSoup(comment_text, 'html.parser'))
            
            # テキストコンテンツを統合
            if options.get('content', True):
                texts = []
                for elem in matching_elements:
                    try:
                        if hasattr(elem, 'get_text'):
                            text = elem.get_text(strip=True)
                            if text:
                                texts.append(text)
                    except Exception:
                        pass
                
                if texts:
                    unique_texts = set(texts)
                    if len(unique_texts) == 1:
                        # すべて同じテキスト
                        stats['commonElements'] += 1
                    else:
                        # テキストが異なる場合は変数化
                        var_name = f"VAR_TEXT_{variable_counter}"
                        variable_counter += 1
                        stats['variableElements'] += 1
                        stats['variables'].append({
                            'name': var_name,
                            'type': 'content',
                            'element': current_path,
                            'description': f"テキスト内容（複数の値が存在: {', '.join(list(unique_texts)[:3])}）"
                        })
                        
                        # テキストを変数プレースホルダーに置換
                        try:
                            if hasattr(base_elem, 'string') and base_elem.string:
                                base_elem.string = f"{{{{ {var_name} }}}}"
                            else:
                                # 子要素をクリアして変数を挿入
                                for child in list(base_elem.children):
                                    if hasattr(child, 'get_text') and child.get_text(strip=True):
                                        child.decompose()
                                base_elem.append(BeautifulSoup(f"{{{{ {var_name} }}}}", 'html.parser'))
                        except Exception:
                            pass
            
            # 子要素を再帰的に統合
            if hasattr(base_elem, 'children'):
                for child in list(base_elem.children):
                    if hasattr(child, 'name') and child.name:
                        try:
                            merge_element_gcd(child, other_files, current_path)
                        except Exception:
                            pass
        
        return base_elem
    
    def get_element_selector_for_gcd(elem):
        """要素のセレクタを取得（最大公約数用）"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        selector = elem.name
        
        # IDがあれば追加（IDは一意なので優先）
        if hasattr(elem, 'attrs') and 'id' in elem.attrs:
            selector += f"#{elem.attrs['id']}"
        # クラスがあれば追加（最初のクラスのみ）
        elif hasattr(elem, 'attrs') and 'class' in elem.attrs:
            classes = elem.attrs['class']
            if isinstance(classes, list) and classes:
                selector += '.' + classes[0]
            elif classes:
                selector += f".{classes}"
        
        return selector
    
    # body要素を統合
    if base_soup.body:
        merge_element_gcd(base_soup.body, parsed_files[1:])
    
    # head要素も統合（スタイルなど）
    if options.get('styles', True) and base_soup.head:
        merge_element_gcd(base_soup.head, parsed_files[1:])
    
    # 統計を更新
    stats['mergedElements'] = stats['commonElements'] + stats['variableElements']
    
    # 変数定義セクションを追加
    if stats['variables']:
        if base_soup.head:
            var_section = base_soup.new_tag('script', type='text/template-variables')
            var_section.string = '\n'.join([
                f"// {v['name']}: {v['description']}"
                for v in stats['variables']
            ])
            base_soup.head.append(var_section)
    
    # 統合されたHTMLを生成
    gcd_html = str(base_soup)
    
    return gcd_html, stats


@app.route('/generate-university-pages', methods=['POST'])
def generate_university_pages():
    """テンプレートを基に27大学のホームページを生成"""
    try:
        data = request.json
        directory = data.get('directory', '')
        template = data.get('template', '')
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        if not template:
            return jsonify({'success': False, 'error': 'テンプレートが指定されていません'}), 400
        
        # ディレクトリの存在確認
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return jsonify({'success': False, 'error': f'ディレクトリが見つかりません: {directory}'}), 404
        
        # HTMLファイルを取得
        html_files = list(dir_path.glob('*.html')) + list(dir_path.glob('*.htm'))
        
        if len(html_files) == 0:
            return jsonify({'success': False, 'error': 'HTMLファイルが見つかりませんでした'}), 404
        
        # テンプレートを解析
        template_soup = BeautifulSoup(template, 'html.parser')
        
        # 出力ディレクトリを作成
        output_dir = dir_path / 'generated_pages'
        output_dir.mkdir(exist_ok=True)
        
        generated_files = []
        success_count = 0
        failed_count = 0
        
        # 各大学のファイルを処理
        for file_path in html_files:
            try:
                # 元のファイルを読み込み
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                original_soup = BeautifulSoup(original_content, 'html.parser')
                
                # テンプレートをコピー
                generated_soup = BeautifulSoup(str(template_soup), 'html.parser')
                
                # 元のファイルからデザイン情報を抽出して適用
                apply_design_to_template(generated_soup, original_soup, file_path.name)
                
                # 生成されたHTMLを保存
                output_filename = f"generated_{file_path.stem}.html"
                output_path = output_dir / output_filename
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(str(generated_soup))
                
                generated_files.append(output_filename)
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Error processing {file_path.name}: {str(e)}")
                continue
        
        return jsonify({
            'success': True,
            'generatedFiles': len(generated_files),
            'successCount': success_count,
            'failedCount': failed_count,
            'files': generated_files,
            'directory': str(output_dir)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def get_element_selector_simple(elem):
    """要素のセレクタを取得（シンプル版）"""
    if not elem or not hasattr(elem, 'name'):
        return ''
    
    selector = elem.name
    
    # IDがあれば追加（IDは一意なので優先）
    if hasattr(elem, 'attrs') and 'id' in elem.attrs:
        selector += f"#{elem.attrs['id']}"
    # クラスがあれば追加（最初のクラスのみ）
    elif hasattr(elem, 'attrs') and 'class' in elem.attrs:
        classes = elem.attrs['class']
        if isinstance(classes, list) and classes:
            selector += '.' + classes[0]
        elif classes:
            selector += f".{classes}"
    
    return selector


def apply_design_to_template(template_soup, original_soup, original_filename):
    """元のHTMLからデザイン情報を抽出してテンプレートに適用（現行デザインを完全再現）"""
    import re
    
    # 1. head要素の完全な適用
    if original_soup.head and template_soup.head:
        # 既存のhead要素をクリア（charset以外）
        for child in list(template_soup.head.children):
            if hasattr(child, 'name') and child.name not in ['meta']:
                child.decompose()
            elif hasattr(child, 'name') and child.name == 'meta' and child.get('charset'):
                continue  # charsetは保持
            elif not hasattr(child, 'name'):
                child.decompose()
        
        # 元のhead要素の内容をコピー
        for child in original_soup.head.children:
            if hasattr(child, 'name'):
                if child.name == 'meta' and child.get('charset'):
                    continue  # charsetは既に存在
                
                # 新しい要素を作成
                new_elem = template_soup.new_tag(child.name)
                if hasattr(child, 'attrs'):
                    for attr, value in child.attrs.items():
                        if isinstance(value, list):
                            new_elem[attr] = value
                        else:
                            new_elem[attr] = value
                
                if hasattr(child, 'string') and child.string:
                    new_elem.string = child.string
                elif hasattr(child, 'contents'):
                    for content in child.contents:
                        if hasattr(content, 'name'):
                            new_elem.append(content)
                        else:
                            new_elem.append(str(content))
                
                template_soup.head.append(new_elem)
    
    # 2. body要素の構造を保持しながらデザインを適用
    def apply_element_design(template_elem, original_elem):
        """要素のデザインを適用"""
        if not template_elem or not original_elem:
            return
        
        # すべての属性を適用（クラス、ID、data属性など）
        if hasattr(original_elem, 'attrs'):
            for attr_name, attr_value in original_elem.attrs.items():
                if attr_name not in ['id'] or template_elem.get('id') != attr_value:
                    if isinstance(attr_value, list):
                        template_elem[attr_name] = attr_value
                    else:
                        template_elem[attr_name] = attr_value
        
        # インラインスタイルを適用
        if original_elem.get('style'):
            template_elem['style'] = original_elem.get('style')
        
        # テキストコンテンツを適用（変数が含まれていない場合）
        if hasattr(original_elem, 'get_text') and hasattr(template_elem, 'string'):
            original_text = original_elem.get_text(strip=True)
            template_text = str(template_elem.string) if template_elem.string else ''
            
            # 変数が含まれていない場合は元のテキストを適用
            if '{{' not in template_text and '}}' not in template_text:
                if original_text and not any(hasattr(c, 'name') for c in template_elem.children if hasattr(c, 'name')):
                    template_elem.string = original_text
    
    # 3. 変数を元の値で置換
    def replace_variables(elem):
        """変数プレースホルダーを元の値で置換"""
        if not elem:
            return
        
        # テキスト内の変数を置換
        if hasattr(elem, 'string') and elem.string:
            text = str(elem.string)
            if '{{' in text and '}}' in text:
                var_matches = re.findall(r'\{\{\s*(\w+)\s*\}\}', text)
                for var_name in var_matches:
                    original_value = find_original_value(original_soup, var_name, elem)
                    if original_value:
                        elem.string = text.replace(f"{{{{ {var_name} }}}}", str(original_value))
        
        # 属性内の変数を置換
        if hasattr(elem, 'attrs'):
            for attr_name, attr_value in list(elem.attrs.items()):
                if isinstance(attr_value, str) and '{{' in attr_value and '}}' in attr_value:
                    var_matches = re.findall(r'\{\{\s*(\w+)\s*\}\}', attr_value)
                    for var_name in var_matches:
                        original_value = find_original_value(original_soup, var_name, elem, attr_name)
                        if original_value:
                            elem.attrs[attr_name] = attr_value.replace(f"{{{{ {var_name} }}}}", str(original_value))
        
        # 子要素を再帰的に処理
        if hasattr(elem, 'children'):
            for child in list(elem.children):
                if hasattr(child, 'name'):
                    replace_variables(child)
    
    # 4. 元のHTMLから対応する要素を探して値を取得
    def find_original_value(original_soup, var_name, template_elem, attr_name=None):
        """元のHTMLから変数に対応する値を探す"""
        selector = get_element_selector_simple(template_elem)
        
        try:
            original_elem = original_soup.select_one(selector)
            if original_elem:
                if attr_name:
                    return original_elem.get(attr_name, '')
                else:
                    return original_elem.get_text(strip=True)
        except Exception:
            pass
        
        return None
    
    # 5. body要素の各要素に対してデザインを適用
    if original_soup.body and template_soup.body:
        # 元のbody要素のすべての要素を取得
        original_elems = original_soup.body.find_all(True)
        
        for orig_elem in original_elems:
            selector = get_element_selector_simple(orig_elem)
            
            try:
                # テンプレート内で対応する要素を探す
                template_elems = template_soup.body.select(selector)
                
                if template_elems:
                    # 最初のマッチした要素にデザインを適用
                    apply_element_design(template_elems[0], orig_elem)
                else:
                    # 要素が見つからない場合は、親要素を探して追加
                    # （構造が異なる場合のフォールバック）
                    pass
            except Exception:
                pass
    
    # 6. 変数を置換
    if template_soup.body:
        replace_variables(template_soup.body)
    
    # 7. body要素の属性を適用（class、id、styleなど）
    if original_soup.body and template_soup.body:
        for attr_name, attr_value in original_soup.body.attrs.items():
            if attr_name not in ['id']:  # idは保持
                template_soup.body[attr_name] = attr_value


@app.route('/download-university-pages', methods=['POST'])
def download_university_pages():
    """生成された27大学のホームページをZIPファイルでダウンロード"""
    try:
        data = request.json
        directory = data.get('directory', '')
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスが指定されていません'}), 400
        
        # 出力ディレクトリ
        output_dir = Path(directory) / 'generated_pages'
        
        if not output_dir.exists():
            return jsonify({'success': False, 'error': '生成されたファイルが見つかりません'}), 404
        
        # 一時ZIPファイルを作成
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        # ZIPファイルを作成
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_dir.glob('*.html'):
                zipf.write(file_path, file_path.name)
        
        return send_file(
            temp_zip.name,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'university_pages_{Path(directory).name}.zip'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/template-merge', methods=['POST', 'OPTIONS'])
def template_merge():
    """複数のHTMLファイルを比較して共通テンプレートを生成"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        files = data.get('files', [])
        options = data.get('options', {})
        
        if len(files) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを選択してください'}), 400
        
        # ファイルを読み込んで解析
        parsed_files = []
        for file_path_str in files:
            # ファイルパスが絶対パスか相対パスかを判定
            file_path = Path(file_path_str)
            
            # 絶対パスでない場合、アップロードフォルダからの相対パスとして扱う
            if not file_path.is_absolute():
                safe_filename = secure_filename(file_path_str)
                file_path = UPLOAD_DIR / safe_filename
            
            if not file_path.exists():
                return jsonify({'success': False, 'error': f'ファイルが見つかりません: {file_path_str}'}), 404
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                return jsonify({'success': False, 'error': f'ファイルの読み込みに失敗しました: {file_path_str} - {str(e)}'}), 500
            
            try:
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'filename': file_path.name,
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                return jsonify({'success': False, 'error': f'ファイルの解析エラー ({filename}): {str(e)}'}), 400
        
        # 共通テンプレートを生成
        merged_template, stats = merge_html_templates(parsed_files, options)
        
        return jsonify({
            'success': True,
            'template': merged_template,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/list-directory-files', methods=['POST', 'OPTIONS'])
def list_directory_files():
    """指定ディレクトリ内のファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        # 空欄の場合はアップロードフォルダを使用
        if not directory:
            directory = str(UPLOAD_DIR)
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。\n'
                        f'または、Linux形式の絶対パス（例: /tmp/html）を指定してください。'
            }), 400
        
        # Windowsパスの処理: バックスラッシュとスラッシュを正規化
        # c:\\html, c:\html, c:/html を正しく処理
        directory = directory.strip()
        # スラッシュをバックスラッシュに変換（Windowsパスの場合）
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            # Windows絶対パス（例: C:\html, C:/html）
            # ドライブレターを大文字に正規化
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            # 相対パスやその他の形式
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        # パスを正規化
        try:
            # Windows絶対パスの場合、Path()で直接処理
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if parent.exists():
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # すべてのファイルを検索（HTML、CSS、その他）
        files = []
        
        # HTMLファイル（識別子情報も抽出）
        for ext in ['*.html', '*.htm']:
            for file_path in dir_path.glob(ext):
                try:
                    file_info = {
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': 'html'
                    }
                    
                    # HTMLファイル内の識別子を抽出
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # IDを抽出
                        ids = set()
                        for elem in soup.find_all(id=True):
                            elem_id = elem.get('id')
                            if elem_id:
                                ids.add(str(elem_id))
                        
                        # クラス名を抽出
                        classes = set()
                        for elem in soup.find_all(class_=True):
                            elem_classes = elem.get('class', [])
                            if isinstance(elem_classes, list):
                                classes.update([str(c) for c in elem_classes if c])
                            elif elem_classes:
                                classes.add(str(elem_classes))
                        
                        # データ属性を抽出
                        data_attrs = set()
                        for elem in soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys())):
                            for attr in elem.attrs:
                                if attr.startswith('data-'):
                                    data_attrs.add(attr)
                        
                        file_info['identifiers'] = {
                            'ids': sorted(list(ids)),
                            'classes': sorted(list(classes)),
                            'data_attrs': sorted(list(data_attrs))
                        }
                    except Exception as e:
                        # HTML解析エラーは無視（識別子情報なしで続行）
                        file_info['identifiers'] = {
                            'ids': [],
                            'classes': [],
                            'data_attrs': []
                        }
                    
                    files.append(file_info)
                except Exception:
                    continue
        
        # CSSファイル
        for file_path in dir_path.glob('*.css'):
            try:
                files.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'type': 'css'
                })
            except Exception:
                continue
        
        # その他のテキストファイル（オプション）
        for ext in ['*.txt', '*.js', '*.json', '*.xml']:
            for file_path in dir_path.glob(ext):
                try:
                    files.append({
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': 'other'
                    })
                except Exception:
                    continue
        
        # ファイル名でソート
        files.sort(key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """アプリケーション設定を取得"""
    try:
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        
        return jsonify({
            'success': True,
            'is_cloud': bool(is_cloud),
            'default_html_directory': None,
            'upload_folder': app.config.get('UPLOAD_FOLDER', 'uploads'),
            'directory_info': None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-directory', methods=['POST', 'OPTIONS'])
def check_directory():
    """指定されたディレクトリの存在確認とファイル一覧を取得"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        if not directory:
            return jsonify({'success': False, 'error': 'ディレクトリパスを指定してください'}), 400
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\nLinux形式の絶対パス（例: /tmp/html）を指定してください。'
            }), 400
        
        # パスの正規化
        try:
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                # Windows絶対パス
                directory = directory[0].upper() + directory[1:].replace('/', '\\')
                dir_path = Path(directory)
            else:
                # Linux形式のパス
                dir_path = Path(directory)
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        exists = dir_path.exists() and dir_path.is_dir()
        
        result = {
            'success': True,
            'directory': directory,
            'exists': exists,
            'is_absolute': dir_path.is_absolute(),
            'parent_exists': dir_path.parent.exists() if dir_path.parent != dir_path else False,
            'parent_path': str(dir_path.parent) if dir_path.parent != dir_path else None
        }
        
        if exists:
            # ファイル一覧を取得
            files = []
            try:
                for file_path in dir_path.iterdir():
                    if file_path.is_file():
                        files.append({
                            'name': file_path.name,
                            'size': file_path.stat().st_size,
                            'modified': file_path.stat().st_mtime
                        })
                result['file_count'] = len(files)
                result['files'] = files[:50]  # 最大50件まで
            except Exception as e:
                result['error'] = f'ファイル一覧の取得に失敗: {str(e)}'
        else:
            result['file_count'] = 0
            result['files'] = []
            if dir_path.parent.exists():
                result['suggestion'] = f'親ディレクトリ（{dir_path.parent}）は存在します。ディレクトリが作成されていない可能性があります。'
            else:
                result['suggestion'] = '指定されたパスとその親ディレクトリが存在しません。'
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load-comparison-files', methods=['POST', 'OPTIONS'])
def load_comparison_files():
    """比較用ファイルリストを読み込む"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        directory = data.get('directory', '').strip()
        
        # 空欄の場合はアップロードフォルダを使用
        if not directory:
            directory = str(UPLOAD_DIR)
        
        # Railway/Heroku環境ではWindowsパスは使用不可
        is_cloud = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO') or os.environ.get('VERCEL')
        if is_cloud and directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
            return jsonify({
                'success': False, 
                'error': f'Windowsパス（{directory}）はクラウド環境では使用できません。\n'
                        f'Linux形式の絶対パス（例: /tmp/html）を直接指定してください。\n'
                        f'アップロードフォルダを使用する場合は、パスを空欄にしてください。'
            }), 400
        
        # Windowsパスの処理: バックスラッシュとスラッシュを正規化
        # c:\\html, c:\html, c:/html を正しく処理
        directory = directory.strip()
        # スラッシュをバックスラッシュに変換（Windowsパスの場合）
        if directory and (directory[0].isalpha() and len(directory) > 1 and directory[1] == ':'):
            # Windows絶対パス（例: C:\html, C:/html）
            # ドライブレターを大文字に正規化
            directory = directory[0].upper() + directory[1:].replace('/', '\\')
        else:
            # 相対パスやその他の形式
            directory = directory.replace('\\\\', '\\').replace('/', '\\')
        
        # パスを正規化
        try:
            # Windows絶対パスの場合、Path()で直接処理
            if directory and len(directory) >= 2 and directory[0].isalpha() and directory[1] == ':':
                dir_path = Path(directory)
            else:
                dir_path = Path(directory).resolve()
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'無効なパス形式です: {directory}。エラー: {str(e)}'
            }), 400
        
        # ディレクトリの存在確認
        if not dir_path.exists():
            # より詳細なエラーメッセージ
            error_msg = f'ディレクトリが見つかりません: {directory}'
            if not dir_path.is_absolute():
                error_msg += f' (絶対パスを指定してください。現在のパス: {dir_path})'
            else:
                # 親ディレクトリの存在確認
                parent = dir_path.parent
                if not parent.exists():
                    error_msg += f' (親ディレクトリも存在しません: {parent})'
                else:
                    error_msg += f' (親ディレクトリは存在します: {parent})'
            if not is_cloud:
                error_msg += f'\nパスの例: C:\\html または C:/html\n絶対パスを指定してください'
            else:
                error_msg += f'\nパスの例: /tmp/html または /app/html\nLinux形式の絶対パスを指定してください'
            return jsonify({'success': False, 'error': error_msg}), 404
        
        if not dir_path.is_dir():
            return jsonify({
                'success': False, 
                'error': f'指定されたパスはディレクトリではありません: {directory}'
            }), 400
        
        # HTMLファイルとCSSファイルを検索（最大27個）
        html_files = []
        css_files = []
        
        for ext in ['*.html', '*.htm']:
            html_files.extend(dir_path.glob(ext))
            html_files.extend(dir_path.glob(ext.upper()))
        
        for ext in ['*.css']:
            css_files.extend(dir_path.glob(ext))
            css_files.extend(dir_path.glob(ext.upper()))
        
        # ファイル名でソート
        html_files = sorted(html_files, key=lambda x: x.name)[:27]
        css_files = sorted(css_files, key=lambda x: x.name)
        
        # HTMLファイルとCSSファイルの関連付け
        html_css_map = {}
        for css_file in css_files:
            css_name = css_file.stem  # 拡張子なしのファイル名
            for html_file in html_files:
                html_name = html_file.stem
                # ファイル名が一致するか、HTMLファイル内で参照されているか確認
                if css_name == html_name or css_name in html_name or html_name in css_name:
                    if html_file.path not in html_css_map:
                        html_css_map[html_file.path] = []
                    html_css_map[html_file.path].append(str(css_file))
        
        files = []
        for file_path in html_files:
            try:
                size = file_path.stat().st_size
                related_css = html_css_map.get(str(file_path), [])
                files.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': size,
                    'type': 'html',
                    'relatedFiles': related_css
                })
            except Exception as e:
                continue
        
        # CSSファイルも追加（HTMLに関連付けられていないものも含む）
        for css_file in css_files:
            try:
                size = css_file.stat().st_size
                # 既にHTMLに関連付けられているCSSはスキップ（重複を避ける）
                is_related = any(str(css_file) in file.get('relatedFiles', []) for file in files)
                if not is_related:
                    files.append({
                        'name': css_file.name,
                        'path': str(css_file),
                        'size': size,
                        'type': 'css',
                        'relatedFiles': []
                    })
            except Exception as e:
                continue
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load-file-content', methods=['GET'])
def load_file_content():
    """ファイルの内容を読み込む"""
    try:
        file_path = request.args.get('path', '')
        if not file_path:
            return jsonify({'success': False, 'error': 'ファイルパスを指定してください'}), 400
        
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404
        
        # セキュリティチェック：指定されたディレクトリ内のファイルのみ許可
        # ここでは簡易的に実装（本番環境ではより厳密なチェックが必要）
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'filename': path.name
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/compare-screens', methods=['POST', 'OPTIONS'])
def compare_screens():
    """複数の画面を比較して差分を検出"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        file_paths = data.get('files', [])
        
        if len(file_paths) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを指定してください'}), 400
        
        # 各ファイルを読み込んで解析
        parsed_files = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                parsed_files.append({
                    'path': file_path,
                    'name': path.name,
                    'soup': soup,
                    'content': content
                })
            except Exception as e:
                continue
        
        if len(parsed_files) < 2:
            return jsonify({'success': False, 'error': '有効なファイルが2つ以上必要です'}), 400
        
        # 比較分析を実行（HTMLとCSSの両方）
        comparison = {}
        base_file = parsed_files[0]
        
        # ベースファイルのCSSを抽出
        base_css = extract_css_from_html(base_file['soup'])
        
        for file_info in parsed_files[1:]:
            # HTML構造の比較
            html_differences = compare_html_structure(base_file['soup'], file_info['soup'])
            
            # CSSの比較
            file_css = extract_css_from_html(file_info['soup'])
            css_differences = []
            
            # インラインCSSの比較
            if base_css['inline_css'] or file_css['inline_css']:
                css_diffs = compare_css(base_css['inline_css'], file_css['inline_css'])
                css_differences.extend(css_diffs)
            
            # すべての差分を統合
            all_differences = html_differences + css_differences
            
            comparison[file_info['path']] = {
                'differences': len(all_differences),
                'htmlDifferences': len(html_differences),
                'cssDifferences': len(css_differences),
                'details': all_differences[:20]  # 最初の20件
            }
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'base_file': base_file['name']
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def extract_css_from_html(soup):
    """HTMLからCSSを抽出"""
    css_content = []
    
    # <style>タグ内のCSS
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            css_content.append(style_tag.string)
    
    # <link rel="stylesheet">で参照されているCSSファイル
    css_files = []
    for link_tag in soup.find_all('link', rel='stylesheet'):
        href = link_tag.get('href', '')
        if href:
            css_files.append(href)
    
    return {
        'inline_css': '\n'.join(css_content),
        'external_css': css_files
    }


def parse_css(css_content):
    """CSSをパースしてルールを抽出"""
    import re
    if not css_content or not css_content.strip():
        return []
    
    rules = []
    
    # メディアクエリを処理
    media_pattern = r'@media[^{]*\{'
    media_blocks = re.split(media_pattern, css_content)
    current_media = None
    
    for i, block in enumerate(media_blocks):
        if i == 0 and '@media' in block:
            # 最初のブロックがメディアクエリの場合
            media_match = re.search(r'@media\s+([^{]+)', block)
            if media_match:
                current_media = media_match.group(1).strip()
            continue
        
        # セレクタとプロパティを抽出
        selector_pattern = r'([^{]+)\{([^}]+)\}'
        matches = re.finditer(selector_pattern, block)
        
        for match in matches:
            selector = match.group(1).strip()
            properties_str = match.group(2).strip()
            
            # プロパティをパース
            properties = {}
            prop_matches = re.finditer(r'([^:]+):\s*([^;]+);?', properties_str)
            for prop_match in prop_matches:
                key = prop_match.group(1).strip()
                value = prop_match.group(2).strip()
                properties[key] = value
            
            if selector:  # 空のセレクタは無視
                rules.append({
                    'selector': selector,
                    'properties': properties,
                    'media': current_media
                })
        
        # メディアクエリのリセット
        if '@media' in block:
            media_match = re.search(r'@media\s+([^{]+)', block)
            if media_match:
                current_media = media_match.group(1).strip()
            else:
                current_media = None
    
    return rules


def compare_css(css1_content, css2_content):
    """2つのCSSを比較して差分を返す"""
    if not css1_content and not css2_content:
        return []
    
    rules1 = parse_css(css1_content) if css1_content else []
    rules2 = parse_css(css2_content) if css2_content else []
    
    differences = []
    
    # セレクタごとに比較
    selectors1 = {rule['selector']: rule for rule in rules1}
    selectors2 = {rule['selector']: rule for rule in rules2}
    
    all_selectors = set(selectors1.keys()) | set(selectors2.keys())
    
    for selector in all_selectors:
        rule1 = selectors1.get(selector)
        rule2 = selectors2.get(selector)
        
        if not rule1:
            differences.append({
                'type': 'missing',
                'path': f"CSS: {selector}",
                'selector': selector,
                'fileType': 'css'
            })
        elif not rule2:
            differences.append({
                'type': 'extra',
                'path': f"CSS: {selector}",
                'selector': selector,
                'fileType': 'css'
            })
        else:
            # プロパティを比較
            props1 = rule1.get('properties', {})
            props2 = rule2.get('properties', {})
            
            all_props = set(props1.keys()) | set(props2.keys())
            prop_diffs = {}
            
            for prop in all_props:
                val1 = props1.get(prop)
                val2 = props2.get(prop)
                
                if val1 != val2:
                    prop_diffs[prop] = {'old': val1, 'new': val2}
            
            if prop_diffs:
                differences.append({
                    'type': 'different',
                    'path': f"CSS: {selector}",
                    'selector': selector,
                    'properties': prop_diffs,
                    'fileType': 'css'
                })
    
    return differences


def compare_html_structure(soup1, soup2):
    """2つのHTML構造を比較して差分を返す"""
    differences = []
    
    # 簡易的な比較（タグ、クラス、ID、主要な属性）
    def get_element_signature(elem):
        if not elem or not hasattr(elem, 'name'):
            return None
        sig = {
            'tag': elem.name,
            'id': elem.get('id', ''),
            'classes': sorted(elem.get('class', [])),
            'text_length': len(elem.get_text(strip=True))
        }
        return sig
    
    def compare_elements(elems1, elems2, path=''):
        max_len = max(len(elems1), len(elems2))
        for i in range(max_len):
            if i >= len(elems1):
                differences.append({
                    'type': 'missing',
                    'path': f"{path}[{i}]",
                    'element': str(elems2[i])[:100] if i < len(elems2) else ''
                })
            elif i >= len(elems2):
                differences.append({
                    'type': 'extra',
                    'path': f"{path}[{i}]",
                    'element': str(elems1[i])[:100]
                })
            else:
                sig1 = get_element_signature(elems1[i])
                sig2 = get_element_signature(elems2[i])
                
                if sig1 != sig2:
                    differences.append({
                        'type': 'different',
                        'path': f"{path}[{i}]",
                        'element1': sig1,
                        'element2': sig2
                    })
                
                # 再帰的に子要素を比較
                if hasattr(elems1[i], 'children') and hasattr(elems2[i], 'children'):
                    compare_elements(
                        [c for c in elems1[i].children if hasattr(c, 'name')],
                        [c for c in elems2[i].children if hasattr(c, 'name')],
                        f"{path}[{i}]"
                    )
    
    # body要素を比較
    body1 = soup1.find('body')
    body2 = soup2.find('body')
    
    if body1 and body2:
        compare_elements(
            [c for c in body1.children if hasattr(c, 'name')],
            [c for c in body2.children if hasattr(c, 'name')],
            'body'
        )
    
    return differences


@app.route('/api/export-comparison-report', methods=['POST'])
def export_comparison_report():
    """比較レポートをCSV形式でエクスポート"""
    try:
        data = request.json
        files = data.get('files', [])
        
        if len(files) < 2:
            return jsonify({'success': False, 'error': '2つ以上のファイルを指定してください'}), 400
        
        # CSVレポートを生成
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow(['ファイル名', 'タイプ', 'パス', 'サイズ (KB)', '要素数', 'リンク数', '画像数', 'CSSルール数', 'インラインCSS', '外部CSS'])
        
        # 各ファイルの情報
        for file_info in files:
            path = Path(file_info['path'])
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    file_type = file_info.get('type', 'other')
                    size_kb = path.stat().st_size / 1024
                    
                    if file_type == 'html':
                        soup = BeautifulSoup(content, 'html.parser')
                        elements = len(soup.find_all())
                        links = len(soup.find_all('a'))
                        images = len(soup.find_all('img'))
                        
                        # CSS情報を抽出
                        css_info = extract_css_from_html(soup)
                        inline_css_rules = parse_css(css_info['inline_css'])
                        external_css_count = len(css_info['external_css'])
                        
                        writer.writerow([
                            file_info['name'],
                            'HTML',
                            file_info['path'],
                            f"{size_kb:.2f}",
                            elements,
                            links,
                            images,
                            len(inline_css_rules),
                            'あり' if css_info['inline_css'] else 'なし',
                            external_css_count
                        ])
                    elif file_type == 'css':
                        css_rules = parse_css(content)
                        writer.writerow([
                            file_info['name'],
                            'CSS',
                            file_info['path'],
                            f"{size_kb:.2f}",
                            '',
                            '',
                            '',
                            len(css_rules),
                            '',
                            ''
                        ])
                    else:
                        writer.writerow([
                            file_info['name'],
                            file_type.upper(),
                            file_info['path'],
                            f"{size_kb:.2f}",
                            '',
                            '',
                            '',
                            '',
                            '',
                            ''
                        ])
                except Exception as e:
                    writer.writerow([file_info['name'], file_info.get('type', 'other'), file_info['path'], 'エラー', '', '', '', '', '', ''])
        
        return jsonify({
            'success': True,
            'report': output.getvalue()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def merge_html_templates(parsed_files, options):
    """HTMLテンプレートを統合する"""
    if not parsed_files:
        return '', {'commonElements': 0, 'diffElements': 0, 'mergedElements': 0, 'differences': []}
    
    # 最初のファイルを基準にする
    base_soup = parsed_files[0]['soup']
    base_filename = parsed_files[0]['filename']
    
    stats = {
        'commonElements': 0,
        'diffElements': 0,
        'mergedElements': 0,
        'differences': []
    }
    
    # ヘルパー関数を先に定義
    def get_element_selector(elem):
        """要素のセレクタを取得"""
        if not elem or not hasattr(elem, 'name'):
            return ''
        
        selector = elem.name
        
        # IDがあれば追加
        if hasattr(elem, 'attrs') and 'id' in elem.attrs:
            selector += f"#{elem.attrs['id']}"
        
        # クラスがあれば追加
        if hasattr(elem, 'attrs') and 'class' in elem.attrs:
            classes = elem.attrs['class']
            if isinstance(classes, list):
                selector += '.' + '.'.join(classes)
            else:
                selector += f".{classes}"
        
        return selector
    
    def normalize_element(elem):
        """要素を正規化（比較用）"""
        if not elem or not hasattr(elem, 'name'):
            return None
        
        normalized = {
            'tag': elem.name,
            'attrs': dict(elem.attrs) if hasattr(elem, 'attrs') else {},
            'text': elem.get_text(strip=True) if hasattr(elem, 'get_text') else ''
        }
        
        # クラスをソート（順序の違いを無視）
        if 'class' in normalized['attrs']:
            normalized['attrs']['class'] = sorted(normalized['attrs']['class']) if isinstance(normalized['attrs']['class'], list) else [normalized['attrs']['class']]
        
        return normalized
    
    def compare_elements(elem1, elem2):
        """2つの要素を比較"""
        norm1 = normalize_element(elem1)
        norm2 = normalize_element(elem2)
        
        if not norm1 or not norm2:
            return False
        
        # タグ名が同じか
        if norm1['tag'] != norm2['tag']:
            return False
        
        # 属性を比較（オプションに応じて）
        if options.get('attributes', True):
            # IDが異なる場合は別要素
            if norm1['attrs'].get('id') != norm2['attrs'].get('id'):
                return False
            
            # クラスを比較（順序は無視）
            class1 = set(norm1['attrs'].get('class', []))
            class2 = set(norm2['attrs'].get('class', []))
            if class1 != class2:
                return False
        
        return True
    
    def merge_element(base_elem, other_files):
        """要素を統合"""
        if not base_elem or not hasattr(base_elem, 'name'):
            return base_elem
        
        # 他のファイルで同じ要素を探す
        matching_elements = [base_elem]
        base_selector = get_element_selector(base_elem)
        
        for other_data in other_files:
            other_soup = other_data['soup']
            try:
                # セレクタで要素を検索
                found = other_soup.select_one(base_selector)
                if found and compare_elements(base_elem, found):
                    matching_elements.append(found)
            except Exception as e:
                # セレクタが無効な場合はスキップ
                pass
        
        # 共通属性を抽出
        if options.get('attributes', True) and matching_elements:
            common_attrs = {}
            if len(matching_elements) == len(other_files) + 1:  # すべてのファイルで見つかった
                # 最初の要素の属性を基準に、共通する属性のみを採用
                base_attrs = dict(matching_elements[0].attrs)
                for key, value in base_attrs.items():
                    # すべての要素で同じ値を持つ属性のみ採用
                    if all(hasattr(elem, 'attrs') and elem.attrs.get(key) == value for elem in matching_elements):
                        common_attrs[key] = value
                    else:
                        stats['differences'].append(f"属性 '{key}' が異なります ({base_selector})")
                        stats['diffElements'] += 1
                
                # 共通属性を設定
                matching_elements[0].attrs.clear()
                matching_elements[0].attrs.update(common_attrs)
                stats['commonElements'] += 1
            else:
                stats['diffElements'] += 1
        
        # 子要素を再帰的に統合
        if hasattr(base_elem, 'children'):
            for child in list(base_elem.children):
                if hasattr(child, 'name') and child.name:
                    try:
                        merge_element(child, other_files)
                    except Exception:
                        # エラーが発生した場合はスキップ
                        pass
            
            # 差異がある子要素を処理
            for other_data in other_files:
                other_soup = other_data['soup']
                try:
                    other_elem = other_soup.select_one(base_selector)
                    if other_elem and hasattr(other_elem, 'children'):
                        base_children_tags = [c.name for c in base_elem.children if hasattr(c, 'name') and c.name]
                        other_children_tags = [c.name for c in other_elem.children if hasattr(c, 'name') and c.name]
                        
                        if base_children_tags != other_children_tags:
                            stats['differences'].append(f"子要素の構造が異なります ({base_selector})")
                except Exception:
                    pass
        
        # テキストコンテンツを統合
        if options.get('content', True) and matching_elements:
            texts = []
            for elem in matching_elements:
                try:
                    if hasattr(elem, 'get_text'):
                        texts.append(elem.get_text(strip=True))
                except Exception:
                    pass
            
            if texts:
                # すべて同じテキストの場合のみ採用
                if len(set(texts)) == 1:
                    stats['commonElements'] += 1
                else:
                    # 差異がある場合は、オプションに応じて処理
                    diff_handling = options.get('diffHandling', 'common')
                    if diff_handling == 'common':
                        # 共通部分のみ採用（空にする）
                        try:
                            if hasattr(base_elem, 'string'):
                                base_elem.string = ''
                            else:
                                for child in list(base_elem.children):
                                    if hasattr(child, 'get_text'):
                                        try:
                                            if child.get_text(strip=True):
                                                child.decompose()
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        stats['diffElements'] += 1
                        if len(texts) >= 2:
                            stats['differences'].append(f"テキストが異なります ({base_selector}): {texts[0][:30]}... vs {texts[1][:30]}...")
                    elif diff_handling == 'comment':
                        # 差異をコメントとして追加
                        try:
                            comment_text = f"<!-- 差異: {', '.join(list(set(texts))[:3])} -->"
                            if hasattr(base_elem, 'insert'):
                                base_elem.insert(0, BeautifulSoup(comment_text, 'html.parser'))
                        except Exception:
                            pass
        
        return base_elem
    
    # body要素を統合
    if base_soup.body:
        merge_element(base_soup.body, parsed_files[1:])
    
    # head要素も統合（スタイルなど）
    if options.get('styles', True) and base_soup.head:
        merge_element(base_soup.head, parsed_files[1:])
    
    # 統計を更新
    stats['mergedElements'] = stats['commonElements']
    
    # 統合されたHTMLを生成
    merged_html = str(base_soup)
    
    return merged_html, stats


def main():
    """メイン関数"""
    # WindowsでUTF-8を有効化
    if sys.platform == 'win32':
        try:
            os.system('chcp 65001 >nul 2>&1')
            # 標準出力のエンコーディングをUTF-8に設定
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    parser = argparse.ArgumentParser(
        description='Webブラウザ上でHTMLファイルを編集するツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python web_html_editor.py
  python web_html_editor.py suikankyo.html
  python web_html_editor.py suikankyo.html --port 5000
  python web_html_editor.py suikankyo.html --host 0.0.0.0 --port 8080
        """
    )
    parser.add_argument(
        'html_file',
        type=str,
        nargs='?',
        default=None,
        help='編集するHTMLファイルのパス（オプション: ブラウザからアップロードも可能）'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='ホストアドレス (デフォルト: 127.0.0.1)'
    )
        # RailwayやHerokuなどのクラウド環境では環境変数PORTを使用
        port_env = os.environ.get('PORT')
        default_port = int(port_env) if port_env else 5000
        print(f"環境変数PORT: {port_env}, デフォルトポート: {default_port}", flush=True)
        parser.add_argument(
            '--port',
            type=int,
            default=default_port,
            help=f'ポート番号 (デフォルト: {default_port}, 環境変数PORTが設定されている場合はそれを使用)'
        )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグモードを有効化'
    )
    
    args = parser.parse_args()
    
    global html_file_path, html_editor
    
    # HTMLファイルが指定されている場合は読み込む
    if args.html_file:
        html_file_path = Path(args.html_file)
        if not html_file_path.exists():
            print(f"エラー: ファイル '{html_file_path}' が見つかりません。")
            sys.exit(1)
        
        try:
            print(f"HTMLファイルを読み込み中: {html_file_path}")
            html_editor = HTMLEditor(str(html_file_path))
            print("読み込み完了！")
        except Exception as e:
            print(f"エラー: ファイルの読み込みに失敗しました: {e}")
            sys.exit(1)
    else:
        print("ファイルが指定されていません。ブラウザからファイルをアップロードしてください。")
    
    try:
        # Flaskアプリケーションのログレベルを設定（Railway環境でのデバッグ用）
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        app.logger.setLevel(logging.INFO)
        app.logger.info("FlaskアプリケーションのログレベルをINFOに設定しました")
        
        # フロントエンドビルドディレクトリの確認
        print(f"\n{'='*60}")
        print(f"フロントエンドビルドディレクトリの確認:")
        print(f"  現在の作業ディレクトリ: {os.getcwd()}")
        print(f"  スクリプトのディレクトリ: {Path(__file__).parent}")
        print(f"  FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR}")
        print(f"  存在確認: {FRONTEND_DIST_DIR.exists()}")
        
        # _find_index_html()でindex.htmlを検索
        index_path = _find_index_html()
        if index_path:
            print(f"  ✓ index.html が見つかりました: {index_path}")
        else:
            print(f"  ✗ index.html が見つかりませんでした")
            print(f"    試したパス:")
            print(f"      - FRONTEND_DIST_DIR: {FRONTEND_DIST_DIR / 'index.html'}")
            for dist_dir in _ALTERNATIVE_PATHS:
                print(f"      - {dist_dir / 'index.html'}")
        
        # _find_assets_dir()でassetsディレクトリを検索
        assets_dir = _find_assets_dir()
        if assets_dir:
            print(f"  ✓ assetsディレクトリが見つかりました: {assets_dir}")
        else:
            print(f"  ✗ assetsディレクトリが見つかりませんでした")
        
        if FRONTEND_DIST_DIR.exists():
            try:
                contents = list(FRONTEND_DIST_DIR.iterdir())
                print(f"  FRONTEND_DIST_DIRの内容: {[str(c.name) for c in contents]}")
            except Exception as e:
                print(f"  ディレクトリの内容を取得できませんでした: {e}")
        print(f"{'='*60}")
        
        url = f"http://{args.host}:{args.port}"
        print(f"\n{'='*60}")
        print(f"Webエディタを起動しました！")
        print(f"{'='*60}")
        print(f"ブラウザで以下のURLを開いてください:")
        print(f"  {url}")
        if not args.html_file:
            try:
                print(f"\n💡 ヒント: 「ファイルをアップロード」ボタンからHTMLファイルをアップロードできます")
            except UnicodeEncodeError:
                print(f"\nヒント: 「ファイルをアップロード」ボタンからHTMLファイルをアップロードできます")
        print(f"\n終了するには Ctrl+C を押してください")
        print(f"{'='*60}\n")
        
        # RailwayやHerokuなどのクラウド環境では0.0.0.0でリッスン
        host = args.host
        railway_env = os.environ.get('RAILWAY_ENVIRONMENT')
        dyno = os.environ.get('DYNO')
        port_env = os.environ.get('PORT')
        print(f"環境変数確認: RAILWAY_ENVIRONMENT={railway_env}, DYNO={dyno}, PORT={port_env}", flush=True)
        if railway_env or dyno or port_env:
            host = '0.0.0.0'
            print(f"Railway環境を検出しました。host={host}, port={args.port}", flush=True)
        
        app.run(host=host, port=args.port, debug=args.debug)
    
    except KeyboardInterrupt:
        print("\n\nプログラムを終了します。")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ==================== 大学データ管理API ====================

@app.route('/api/universities', methods=['GET'])
def get_universities():
    """大学一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM universities ORDER BY code')
        universities = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'universities': universities})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/universities', methods=['POST'])
def create_university():
    """大学を登録"""
    try:
        data = request.json
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        
        if not code or not name:
            return jsonify({'success': False, 'error': '大学コードと名前は必須です'}), 400
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO universities (code, name) 
            VALUES (?, ?)
        ''', (code, name))
        
        university_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'id': university_id})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'この大学コードは既に登録されています'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/page-titles', methods=['GET'])
def get_page_titles():
    """ページタイトル一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM page_titles ORDER BY display_order, title')
        titles = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'titles': titles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/pages', methods=['GET'])
def get_university_pages(university_id):
    """大学のページデータ一覧を取得"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT upd.*, pt.title as page_title
            FROM university_page_data upd
            JOIN page_titles pt ON upd.page_title_id = pt.id
            WHERE upd.university_id = ?
            ORDER BY pt.display_order, pt.title
        ''', (university_id,))
        
        pages = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'pages': pages})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/page/<int:page_title_id>', methods=['GET', 'POST', 'PUT'])
def manage_university_page(university_id, page_title_id):
    """大学のページデータを取得・作成・更新"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if request.method == 'GET':
            cursor.execute('''
                SELECT upd.*, pt.title as page_title
                FROM university_page_data upd
                JOIN page_titles pt ON upd.page_title_id = pt.id
                WHERE upd.university_id = ? AND upd.page_title_id = ?
            ''', (university_id, page_title_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return jsonify({'success': True, 'page': dict(row)})
            else:
                return jsonify({'success': False, 'error': 'ページデータが見つかりません'}), 404
        
        elif request.method in ['POST', 'PUT']:
            data = request.json
            content = data.get('content', '')
            metadata = json.dumps(data.get('metadata', {}), ensure_ascii=False)
            
            cursor.execute('''
                INSERT OR REPLACE INTO university_page_data 
                (university_id, page_title_id, content, metadata, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (university_id, page_title_id, content, metadata))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/university/<int:university_id>/config', methods=['GET', 'POST', 'PUT'])
def manage_university_config(university_id):
    """大学のJSON設定ファイルを管理"""
    try:
        config_file = UNIVERSITY_CONFIG_DIR / f'university_{university_id}.json'
        
        if request.method == 'GET':
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return jsonify({'success': True, 'config': config})
            else:
                # デフォルト設定を返す
                return jsonify({'success': True, 'config': {
                    'layout': {},
                    'display_order': [],
                    'items': {}  # 各項目の属性を管理
                }})
        
        elif request.method in ['POST', 'PUT']:
            data = request.json
            config = data.get('config', {})
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-university-page', methods=['POST'])
def generate_university_page():
    """共通テンプレートと大学データを統合してページを生成"""
    try:
        data = request.json
        university_id = data.get('university_id')
        page_title_id = data.get('page_title_id')
        template_html = data.get('template', '')
        
        if not university_id or not page_title_id or not template_html:
            return jsonify({'success': False, 'error': '必要なパラメータが不足しています'}), 400
        
        # 大学データを取得
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT upd.content, upd.metadata, pt.title as page_title
            FROM university_page_data upd
            JOIN page_titles pt ON upd.page_title_id = pt.id
            WHERE upd.university_id = ? AND upd.page_title_id = ?
        ''', (university_id, page_title_id))
        
        page_data = cursor.fetchone()
        
        # 大学設定を取得
        config_file = UNIVERSITY_CONFIG_DIR / f'university_{university_id}.json'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {'layout': {}, 'display_order': [], 'items': {}}
        
        conn.close()
        
        # テンプレートを解析
        soup = BeautifulSoup(template_html, 'html.parser')
        
        # 大学データをテンプレートに埋め込む
        if page_data:
            content = page_data['content'] or ''
            metadata = json.loads(page_data['metadata'] or '{}')
            
            # コンテンツエリアを探して置き換え
            content_area = soup.find(id='content') or soup.find(class_='content') or soup.find('main')
            if content_area:
                content_area.clear()
                content_soup = BeautifulSoup(content, 'html.parser')
                content_area.append(content_soup)
        
        # レイアウト設定を適用
        layout = config.get('layout', {})
        display_order = config.get('display_order', [])
        items_config = config.get('items', {})  # 各項目の属性設定
        
        # 各項目の属性を適用
        if items_config:
            for item_id, item_attrs in items_config.items():
                # ID、クラス、data属性などで要素を検索
                element = None
                
                # IDで検索
                if item_attrs.get('id'):
                    element = soup.find(id=item_attrs['id'])
                
                # クラスで検索
                if not element and item_attrs.get('class'):
                    classes = item_attrs['class']
                    if isinstance(classes, str):
                        classes = [classes]
                    element = soup.find(class_=classes[0]) if classes else None
                
                # data属性で検索
                if not element and item_attrs.get('data_attr'):
                    data_attr = item_attrs['data_attr']
                    element = soup.find(attrs={data_attr: item_id})
                
                if element:
                    # 表示/非表示
                    if item_attrs.get('visible') is False:
                        element['style'] = (element.get('style', '') + '; display: none;').strip('; ')
                    elif item_attrs.get('visible') is True:
                        # 表示する場合は既存のdisplay:noneを削除
                        style = element.get('style', '')
                        style = style.replace('display: none;', '').replace('display:none;', '')
                        element['style'] = style.strip('; ')
                    
                    # 位置（order）
                    if 'order' in item_attrs:
                        element['style'] = (element.get('style', '') + f'; order: {item_attrs["order"]};').strip('; ')
                    
                    # CSSスタイル
                    if item_attrs.get('styles'):
                        existing_style = element.get('style', '')
                        for prop, value in item_attrs['styles'].items():
                            # CSSプロパティ名をケバブケースに変換
                            css_prop = prop.replace('_', '-')
                            existing_style = existing_style.replace(f'{css_prop}:', '').strip('; ')
                            existing_style = (existing_style + f'; {css_prop}: {value};').strip('; ')
                        element['style'] = existing_style
                    
                    # クラスの追加/削除
                    if item_attrs.get('add_classes'):
                        add_classes = item_attrs['add_classes']
                        if isinstance(add_classes, str):
                            add_classes = [add_classes]
                        existing_classes = element.get('class', [])
                        if isinstance(existing_classes, str):
                            existing_classes = [existing_classes]
                        element['class'] = list(set(existing_classes + add_classes))
                    
                    if item_attrs.get('remove_classes'):
                        remove_classes = item_attrs['remove_classes']
                        if isinstance(remove_classes, str):
                            remove_classes = [remove_classes]
                        existing_classes = element.get('class', [])
                        if isinstance(existing_classes, str):
                            existing_classes = [existing_classes]
                        element['class'] = [cls for cls in existing_classes if cls not in remove_classes]
                    
                    # 属性の追加/変更
                    if item_attrs.get('attributes'):
                        for attr_name, attr_value in item_attrs['attributes'].items():
                            element[attr_name] = attr_value
                    
                    # テキストコンテンツの変更
                    if 'text_content' in item_attrs:
                        element.string = item_attrs['text_content']
                    
                    # HTMLコンテンツの変更
                    if 'html_content' in item_attrs:
                        element.clear()
                        html_soup = BeautifulSoup(item_attrs['html_content'], 'html.parser')
                        element.append(html_soup)
        
        # 表示順序に従って要素を並び替え
        if display_order:
            body = soup.find('body')
            if body:
                sections = {}
                for elem in body.find_all(['section', 'div'], class_=True):
                    classes = elem.get('class', [])
                    for cls in classes:
                        if cls in display_order:
                            sections[cls] = elem
                            break
                
                # 順序に従って再配置
                for cls in display_order:
                    if cls in sections:
                        body.append(sections[cls])
        
        generated_html = str(soup)
        
        return jsonify({
            'success': True,
            'html': generated_html,
            'page_title': page_data['title'] if page_data else None
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== YAML設定ファイルベースのページ生成 ====================

def load_yaml_config():
    """YAML設定ファイルを読み込む"""
    config_path = Path(__file__).parent / 'university_pages_config.yml'
    if not config_path.exists():
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_form_field_html(field_config):
    """フォームフィールドの設定からHTMLを生成"""
    field_type = field_config.get('type', 'text')
    name = field_config.get('name', '')
    label = field_config.get('label', '')
    required = field_config.get('required', False)
    
    html_parts = []
    
    # ラベル
    if label and field_type not in ['section', 'navigation']:
        required_mark = ' <span style="color: red;">*</span>' if required else ''
        html_parts.append(f'<label for="{name}" style="display: block; margin-bottom: 5px; font-weight: 600;">{label}{required_mark}</label>')
    
    # フィールド本体
    if field_type == 'text':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="text" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'textarea':
        required_attr = 'required' if required else ''
        html_parts.append(f'<textarea id="{name}" name="{name}" class="form-control" {required_attr} rows="4" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;"></textarea>')
    
    elif field_type == 'date':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="date" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'tel':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="tel" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'email':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="email" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'number':
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="number" id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'select':
        options = field_config.get('options', [])
        required_attr = 'required' if required else ''
        options_html = ''.join([f'<option value="{opt}">{opt}</option>' for opt in options])
        html_parts.append(f'<select id="{name}" name="{name}" class="form-control" {required_attr} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">{options_html}</select>')
    
    elif field_type == 'checkbox':
        checked_attr = 'checked' if field_config.get('checked', False) else ''
        required_attr = 'required' if required else ''
        html_parts.append(f'<input type="checkbox" id="{name}" name="{name}" {checked_attr} {required_attr} style="margin-right: 5px; margin-bottom: 15px;">')
    
    elif field_type == 'radio':
        options = field_config.get('options', [])
        required_attr = 'required' if required else ''
        radio_html = []
        for opt in options:
            radio_id = f"{name}_{opt}"
            radio_html.append(f'<div style="margin-bottom: 10px;"><input type="radio" id="{radio_id}" name="{name}" value="{opt}" {required_attr} style="margin-right: 5px;"><label for="{radio_id}">{opt}</label></div>')
        html_parts.append(''.join(radio_html))
    
    elif field_type == 'file':
        accept = field_config.get('accept', '')
        multiple = 'multiple' if field_config.get('multiple', False) else ''
        required_attr = 'required' if required else ''
        accept_attr = f'accept="{accept}"' if accept else ''
        html_parts.append(f'<input type="file" id="{name}" name="{name}" class="form-control" {required_attr} {accept_attr} {multiple} style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">')
    
    elif field_type == 'section':
        html_parts.append(f'<h2 style="margin-top: 30px; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #667eea;">{label}</h2>')
    
    elif field_type == 'navigation':
        html_parts.append(f'<nav style="margin-bottom: 20px;"><ul style="list-style: none; padding: 0;">{label}</ul></nav>')
    
    return '\n'.join(html_parts)


def generate_page_html(page_config, university_config=None, generation_settings=None):
    """ページ設定からHTMLを生成"""
    page_title = page_config.get('title', '')
    page_id = page_config.get('id', '')
    description = page_config.get('description', '')
    form_fields = page_config.get('form_fields', [])
    
    # 大学のカスタマイズ設定を取得
    custom_fields = []
    if university_config:
        for custom_page in university_config.get('custom_pages', []):
            if custom_page.get('page_title_id') == page_id:
                custom_fields = custom_page.get('custom_fields', [])
                break
    
    # HTMLの生成
    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="ja">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{page_title}</title>')
    
    # CSSフレームワークの設定
    css_framework = generation_settings.get('template', {}).get('css_framework', 'bootstrap') if generation_settings else 'bootstrap'
    if css_framework == 'bootstrap':
        html_parts.append('    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">')
    html_parts.append('    <style>')
    html_parts.append('        body { font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif; padding: 20px; background-color: #f5f5f5; }')
    html_parts.append('        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
    html_parts.append('        .form-control { margin-bottom: 15px; }')
    html_parts.append('        .btn-submit { background-color: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }')
    html_parts.append('        .btn-submit:hover { background-color: #5568d3; }')
    html_parts.append('        .description { color: #666; margin-bottom: 20px; }')
    html_parts.append('    </style>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="container">')
    html_parts.append(f'        <h1>{page_title}</h1>')
    if description:
        html_parts.append(f'        <p class="description">{description}</p>')
    
    html_parts.append('        <form id="admissionForm" method="POST" action="#" enctype="multipart/form-data">')
    
    # カスタムフィールド（before位置）を挿入
    for custom_field in custom_fields:
        if custom_field.get('position') == 'before':
            target = custom_field.get('target_field', '')
            # ターゲットフィールドの前に挿入
            html_parts.append(generate_form_field_html(custom_field))
    
    # 通常のフォームフィールド
    for field in form_fields:
        html_parts.append(generate_form_field_html(field))
    
    # カスタムフィールド（after位置）を挿入
    for custom_field in custom_fields:
        if custom_field.get('position') != 'before':
            html_parts.append(generate_form_field_html(custom_field))
    
    html_parts.append('            <div style="margin-top: 30px; text-align: center;">')
    html_parts.append('                <button type="submit" class="btn-submit">送信</button>')
    html_parts.append('                <button type="button" onclick="history.back()" style="margin-left: 10px; padding: 12px 30px; background-color: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">戻る</button>')
    html_parts.append('            </div>')
    html_parts.append('        </form>')
    html_parts.append('    </div>')
    
    # JavaScript
    html_parts.append('    <script>')
    html_parts.append('        document.getElementById("admissionForm").addEventListener("submit", function(e) {')
    html_parts.append('            e.preventDefault();')
    html_parts.append('            // フォーム送信処理をここに実装')
    html_parts.append('            alert("送信機能は実装されていません");')
    html_parts.append('        });')
    html_parts.append('    </script>')
    html_parts.append('</body>')
    html_parts.append('</html>')
    
    return '\n'.join(html_parts)


@app.route('/api/generate-pages-from-yaml', methods=['POST'])
def generate_pages_from_yaml():
    """YAML設定ファイルを基に指定した大学または全大学の入学手続きWEBページを生成"""
    try:
        data = request.json
        university_codes = data.get('university_codes', [])  # 空の場合は全大学
        output_directory = data.get('output_directory', '')
        
        # YAML設定ファイルを読み込む
        yaml_config = load_yaml_config()
        if not yaml_config:
            return jsonify({'success': False, 'error': 'YAML設定ファイルが見つかりません'}), 404
        
        default_page_titles = yaml_config.get('default_page_titles', [])
        universities_config = yaml_config.get('universities', [])
        generation_settings = yaml_config.get('generation_settings', {})
        page_mappings = yaml_config.get('page_mappings', [])
        
        # 出力ディレクトリの設定
        if output_directory:
            output_dir = Path(output_directory)
        else:
            output_dir = UPLOAD_DIR / 'generated_university_pages'
        
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # データベースから大学情報を取得
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 対象大学を決定
        if university_codes:
            # 指定された大学コードの大学を取得
            placeholders = ','.join(['?' for _ in university_codes])
            cursor.execute(f'SELECT * FROM universities WHERE code IN ({placeholders})', university_codes)
        else:
            # 全大学を取得
            cursor.execute('SELECT * FROM universities ORDER BY code')
        
        universities = cursor.fetchall()
        conn.close()
        
        if not universities:
            return jsonify({'success': False, 'error': '対象となる大学が見つかりませんでした'}), 404
        
        generated_files = []
        total_pages = 0
        success_count = 0
        failed_count = 0
        
        # 各大学に対してページを生成
        for university in universities:
            university_code = university['code']
            university_name = university['name']
            university_id = university['id']
            
            # 大学の設定を取得
            university_config = None
            for univ_config in universities_config:
                if univ_config.get('code') == university_code:
                    university_config = univ_config
                    break
            
            # 大学ごとの出力ディレクトリを作成
            univ_output_dir = output_dir / f"{university_code}_{university_name}"
            univ_output_dir.mkdir(exist_ok=True, parents=True)
            
            # 各ページタイトルに対してページを生成
            for page_config in default_page_titles:
                try:
                    page_id = page_config.get('id')
                    page_title = page_config.get('title', '')
                    
                    # ページマッピングからファイル名を取得
                    file_name = f"page_{page_id}_{page_title}.html"
                    route = f"/page-{page_id}"
                    for mapping in page_mappings:
                        if mapping.get('page_title_id') == page_id:
                            file_name = mapping.get('file_name', file_name)
                            route = mapping.get('route', route)
                            break
                    
                    # HTMLを生成
                    html_content = generate_page_html(
                        page_config,
                        university_config,
                        generation_settings
                    )
                    
                    # ファイルに保存
                    output_file = univ_output_dir / file_name
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    generated_files.append({
                        'university_code': university_code,
                        'university_name': university_name,
                        'page_id': page_id,
                        'page_title': page_title,
                        'file_name': file_name,
                        'file_path': str(output_file)
                    })
                    
                    total_pages += 1
                    success_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Error generating page {page_id} for {university_code}: {str(e)}")
                    continue
        
        return jsonify({
            'success': True,
            'message': f'{len(universities)}大学、合計{total_pages}ページを生成しました',
            'universities_count': len(universities),
            'total_pages': total_pages,
            'success_count': success_count,
            'failed_count': failed_count,
            'output_directory': str(output_dir),
            'generated_files': generated_files
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-pages-from-yaml-download', methods=['POST'])
def generate_pages_from_yaml_download():
    """YAML設定ファイルを基に生成したページをZIPファイルでダウンロード"""
    try:
        data = request.json
        output_directory = data.get('output_directory', '')
        
        if not output_directory:
            output_directory = str(UPLOAD_DIR / 'generated_university_pages')
        
        output_dir = Path(output_directory)
        if not output_dir.exists():
            return jsonify({'success': False, 'error': '出力ディレクトリが見つかりません'}), 404
        
        # ZIPファイルを作成
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in output_dir.rglob('*.html'):
                arcname = file_path.relative_to(output_dir)
                zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'university_pages_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/<path:path>')
def catch_all(path):
    """SPAルーティング用のキャッチオールルート - APIルート以外はすべてindex.htmlを返す"""
    # APIルートの場合は404を返す
    if path.startswith('api/') or path.startswith('save') or path.startswith('upload') or \
       path.startswith('files') or path.startswith('search') or path.startswith('structure') or \
       path.startswith('validate') or path.startswith('download') or path.startswith('favicon.ico') or \
       path.startswith('assets/'):
        return jsonify({'error': 'Not found'}), 404
    
    # それ以外はReactアプリを返す
    return _serve_index_html()


if __name__ == "__main__":
    main()

