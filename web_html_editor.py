#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebベースHTMLエディタ
ブラウザ上でHTMLファイルを編集できるWebアプリケーション
"""

import os
import sys
import argparse
import shutil
import tempfile
import traceback
import base64
import json
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for
from html_editor import HTMLEditor

app = Flask(__name__)

# Vercel環境では/tmpディレクトリを使用
if os.environ.get('VERCEL'):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB制限

html_editor = None
html_file_path = None

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


# HTMLエディタのテンプレート
EDITOR_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTMLエディタ{% if filename %} - {{ filename }}{% endif %}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 {
            font-size: 24px;
            margin-bottom: 5px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
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
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .toolbar {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: flex !important;
            gap: 10px;
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
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            font-weight: 500;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
        }
        .btn-success {
            background: #48bb78;
            color: white;
        }
        .btn-success:hover {
            background: #38a169;
        }
        .btn-info {
            background: #4299e1;
            color: white;
        }
        .btn-info:hover {
            background: #3182ce;
        }
        .btn-danger {
            background: #f56565;
            color: white;
        }
        .btn-danger:hover {
            background: #e53e3e;
        }
        .editor-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 1024px) {
            .editor-container {
                grid-template-columns: 1fr;
            }
        }
        .editor-panel {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .panel-header {
            background: #f7fafc;
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
            font-weight: 600;
            color: #2d3748;
        }
        .editor {
            width: 100%;
            height: 600px;
            border: none;
            padding: 15px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            background: #1e1e1e;
            color: #d4d4d4;
        }
        .preview {
            width: 100%;
            height: 600px;
            border: none;
            background: white;
        }
        .info-panel {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
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
            color: #4a5568;
            margin-bottom: 5px;
            font-size: 14px;
        }
        .info-value {
            color: #2d3748;
            font-size: 13px;
        }
        .status {
            padding: 10px 15px;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        .status.success {
            background: #c6f6d5;
            color: #22543d;
            border: 1px solid #9ae6b4;
        }
        .status.error {
            background: #fed7d7;
            color: #742a2a;
            border: 1px solid #fc8181;
        }
        .search-box {
            flex: 1;
            min-width: 200px;
            padding: 10px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 14px;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
        }
        .modal-content {
            background: white;
            margin: 10% auto;
            padding: 30px;
            border-radius: 8px;
            width: 90%;
            max-width: 600px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: #000;
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
            padding: 10px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 14px;
        }
        .btn-warning {
            background: #f59e0b;
            color: white;
        }
        .btn-warning:hover {
            background: #d97706;
        }
        .error-item {
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 4px;
            border-left: 4px solid;
        }
        .error-item.error {
            background: #fee;
            border-color: #f56565;
        }
        .error-item.warning {
            background: #fffbeb;
            border-color: #f59e0b;
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
    
    <div class="container">
        <!-- ファイル操作ボタン（常に表示、別ツールバー） -->
        <div id="fileToolbar" style="background: #f0f4f8; padding: 15px; border-radius: 8px; margin-bottom: 15px; display: flex !important; gap: 10px; align-items: center; flex-wrap: wrap; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <button class="btn btn-primary" onclick="showUploadModal()" id="uploadBtnMain" style="font-weight: 600; padding: 12px 24px; background: #667eea; border: 2px solid #5568d3; color: white; display: inline-block !important; visibility: visible !important; opacity: 1 !important; position: relative !important; z-index: 100 !important; margin-right: 10px; flex-shrink: 0; cursor: pointer;">
                📤 ファイルをアップロード
            </button>
            <button class="btn btn-success" onclick="downloadFile()" id="downloadBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; padding: 12px 24px; background: #48bb78; border-color: #38a169; color: white; display: inline-block !important; visibility: visible !important; opacity: {% if filename %}1{% else %}0.5{% endif %} !important; position: relative !important; z-index: 100 !important; margin-right: 10px; flex-shrink: 0; cursor: {% if filename %}pointer{% else %}not-allowed{% endif %};">
                ⬇️ ダウンロード
            </button>
            <button class="btn btn-info" onclick="showFileList()" id="fileListBtn" style="display: inline-block !important; visibility: visible !important; margin-right: 10px; flex-shrink: 0;">📁 ファイル一覧</button>
        </div>
        
        <!-- 編集操作ボタン -->
        <div class="toolbar" id="mainToolbar" style="display: flex !important;">
            <button class="btn btn-primary" onclick="saveFile()" id="saveBtn" {% if not filename %}disabled{% endif %}>💾 保存</button>
            <button class="btn btn-success" onclick="reloadFile()" id="reloadBtn" {% if not filename %}disabled{% endif %}>🔄 再読み込み</button>
            <button class="btn btn-danger" onclick="clearEditor()" id="clearBtn">🗑️ クリア</button>
            <button class="btn btn-info" onclick="showStructure()" id="structureBtn" {% if not filename %}disabled{% endif %}>📊 構造情報</button>
            <button class="btn btn-warning" onclick="validateHTML()" id="validateBtn" {% if not filename %}disabled{% endif %}>⚠️ 構文チェック</button>
            <button class="btn btn-info" onclick="showSearch()" id="searchBtn" {% if not filename %}disabled{% endif %}>🔍 検索・置換</button>
            <input type="text" id="searchBox" class="search-box" placeholder="ID、クラス、タグで検索..." onkeypress="if(event.key==='Enter') searchElement()" {% if not filename %}disabled{% endif %}>
            <button class="btn btn-info" onclick="searchElement()" id="searchElementBtn" {% if not filename %}disabled{% endif %}>検索</button>
        </div>
        
        <div id="errorPanel" style="display: none; background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 15px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; color: #856404;">⚠️ 構文エラー・警告</h3>
                <button onclick="document.getElementById('errorPanel').style.display='none'" style="background: #ffc107; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">閉じる</button>
            </div>
            <div id="errorList"></div>
        </div>
        
        <div id="status" class="status"></div>
        
        <div class="editor-container">
            <div class="editor-panel">
                <div class="panel-header">📄 HTMLソース</div>
                <textarea id="htmlEditor" class="editor" spellcheck="false" data-filename="{{ filename|e }}" data-has-content="{% if has_content %}true{% else %}false{% endif %}"></textarea>
            </div>
            <div class="editor-panel">
                <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <span>👁️ プレビュー</span>
                    <button class="btn btn-success" onclick="downloadPreview()" id="downloadPreviewBtn" style="font-size: 12px; padding: 6px 12px; margin-left: 10px;" title="プレビューをHTMLファイルとしてダウンロード">
                        ⬇️ HTMLとして保存
                    </button>
                </div>
                <iframe id="preview" class="preview" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe>
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
            {% else %}
            <div class="info-item">
                <div class="info-value" style="text-align: center; padding: 40px; color: #718096;">
                    <p style="font-size: 18px; margin-bottom: 15px;">📁 ファイルが選択されていません</p>
                    <p style="font-size: 14px; margin-bottom: 20px;">HTMLファイルをアップロードして編集を開始してください</p>
                    <button class="btn btn-primary" onclick="showUploadModal()" style="padding: 15px 30px; font-size: 16px; font-weight: 600;">
                        📤 HTMLファイルをアップロード
                    </button>
                    <p style="font-size: 12px; margin-top: 15px; color: #a0aec0;">または「ファイル一覧」から既存のファイルを選択</p>
                </div>
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
        <div class="modal-content" style="max-width: 800px;">
            <span class="close" onclick="closeModal('fileListModal')">&times;</span>
            <h2>📁 ファイル一覧</h2>
            <div id="fileListContent" style="margin-top: 20px;">
                <p>読み込み中...</p>
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
            
            // エディタの変更をプレビューに反映
            if (editor && preview) {
                editor.addEventListener('input', function() {
                    updatePreview();
                });
            }
        });
        
        // プレビューを更新
        function updatePreview() {
            const editor = getEditor();
            const preview = document.getElementById('preview');
            if (!editor || !preview) return;
            
            let content = editor.value;
            
            // CSSの読み込みを修正: rel="preload" を rel="stylesheet" に変換
            // これにより、Blob URLのコンテキストでもCSSが正しく読み込まれる
            content = content.replace(
                /<link\s+rel=["']preload["']\s+href=["']([^"']+)["']\s+as=["']style["']\s+onload=["']([^"']*)["']/gi,
                '<link rel="stylesheet" href="$1"'
            );
            
            // 相対パスのCSS/JS/画像を絶対URLに変換
            // Blob URLのコンテキストでは相対パスが解決されないため、絶対URLに変換する必要がある
            const currentFilename = window.editorFilename || '';
            let baseUrl = window.location.origin;
            
            // ファイル名からベースパスを推測（相対パスの解決に使用）
            // 例: ../common/css/style.css の場合、元のファイルのパスを基準に解決
            if (currentFilename) {
                // ファイル名からディレクトリパスを取得
                const filePath = currentFilename.split('/');
                filePath.pop(); // ファイル名を削除
                const dirPath = filePath.join('/');
                if (dirPath) {
                    baseUrl = window.location.origin + '/' + dirPath;
                }
            }
            
            // 相対パス（../ で始まる、または / で始まらない、かつ http:// や https:// で始まらない）を絶対URLに変換
            // href属性の相対パスを変換
            content = content.replace(
                /(<link[^>]*href=["'])(?!https?:\/\/|\/\/|data:)([^"']+)(["'][^>]*>)/gi,
                function(match, prefix, path, suffix) {
                    // 絶対URLやdata URIの場合はそのまま
                    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//') || path.startsWith('data:')) {
                        return match;
                    }
                    // 相対パスを絶対URLに変換
                    let absolutePath = path;
                    if (path.startsWith('../')) {
                        // ../ で始まる場合は、ベースURLから相対的に解決
                        // 簡易的な実装: ../ を削除してベースURLに追加
                        absolutePath = baseUrl.replace(/\/[^\/]*$/, '') + '/' + path.replace(/^\.\.\//, '');
                    } else if (path.startsWith('./')) {
                        absolutePath = baseUrl + '/' + path.substring(2);
                    } else if (!path.startsWith('/')) {
                        absolutePath = baseUrl + '/' + path;
                    } else {
                        absolutePath = window.location.origin + path;
                    }
                    return prefix + absolutePath + suffix;
                }
            );
            
            // src属性の相対パスを変換
            content = content.replace(
                /(<(?:img|script|iframe)[^>]*src=["'])(?!https?:\/\/|\/\/|data:)([^"']+)(["'][^>]*>)/gi,
                function(match, prefix, path, suffix) {
                    // 絶対URLやdata URIの場合はそのまま
                    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//') || path.startsWith('data:')) {
                        return match;
                    }
                    // 相対パスを絶対URLに変換
                    let absolutePath = path;
                    if (path.startsWith('../')) {
                        absolutePath = baseUrl.replace(/\/[^\/]*$/, '') + '/' + path.replace(/^\.\.\//, '');
                    } else if (path.startsWith('./')) {
                        absolutePath = baseUrl + '/' + path.substring(2);
                    } else if (!path.startsWith('/')) {
                        absolutePath = baseUrl + '/' + path;
                    } else {
                        absolutePath = window.location.origin + path;
                    }
                    return prefix + absolutePath + suffix;
                }
            );
            
            const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            
            // 以前のBlob URLを解放（メモリリークを防ぐ）
            if (preview.dataset.blobUrl) {
                URL.revokeObjectURL(preview.dataset.blobUrl);
            }
            preview.dataset.blobUrl = url;
            
            preview.src = url;
        }
        
        // ボタンの表示を確認・強制表示
        function ensureButtonsVisible() {
            const uploadBtn = document.getElementById('uploadBtnMain');
            const downloadBtn = document.getElementById('downloadBtn');
            const toolbar = document.getElementById('mainToolbar');
            
            console.log('Checking buttons visibility...');
            console.log('Upload button:', uploadBtn);
            console.log('Download button:', downloadBtn);
            console.log('Toolbar:', toolbar);
            
            if (uploadBtn) {
                uploadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 1 !important; position: relative !important; z-index: 100 !important; font-weight: 600; padding: 12px 24px; background: #667eea; border: 2px solid #5568d3;';
                console.log('Upload button styled');
            } else {
                console.error('Upload button not found!');
            }
            
            if (downloadBtn) {
                if (downloadBtn.disabled) {
                    downloadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 0.5 !important; position: relative !important; z-index: 100 !important;';
                } else {
                    downloadBtn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 1 !important; position: relative !important; z-index: 100 !important; font-weight: 600; padding: 12px 24px; background: #48bb78; border-color: #38a169;';
                }
                console.log('Download button styled');
            } else {
                console.error('Download button not found!');
            }
            
            if (toolbar) {
                toolbar.style.cssText = 'display: flex !important; gap: 10px; flex-wrap: wrap; align-items: center; overflow-x: auto; background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); min-height: 60px;';
                console.log('Toolbar styled');
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
        async function showStructure() {
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
        
        // 要素を検索
        async function searchElement() {
            const query = document.getElementById('searchBox').value.trim();
            if (!query) {
                showStatus('検索文字列を入力してください', 'error');
                return;
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
                    if (data.results.length > 0) {
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
                        
                        let message = `検索結果: ${data.results.length}個見つかりました\n`;
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
                        if (byType.source.length > 0) {
                            message += `ソース: ${byType.source[0].count || byType.source.length}箇所 `;
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
        
        // 検索モーダルを表示
        function showSearch() {
            document.getElementById('searchModal').style.display = 'block';
        }
        
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
            if (content.includes(searchText)) {
                const newContent = content.replace(new RegExp(searchText, 'g'), replaceText);
                editor.value = newContent;
                updatePreview();
                showStatus('置換しました', 'success');
                closeModal('searchModal');
            } else {
                showStatus('検索文字列が見つかりませんでした', 'error');
            }
        };
        
        // モーダルを閉じる
        function closeModal(modalId) {
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
        function showUploadModal() {
            document.getElementById('uploadModal').style.display = 'block';
        }
        
        // ファイル一覧を表示
        async function showFileList() {
            try {
                const response = await fetch('/files');
                const data = await response.json();
                if (data.success) {
                    let html = '<div style="max-height: 400px; overflow-y: auto;">';
                    if (data.files.length > 0) {
                        html += '<table style="width: 100%; border-collapse: collapse;">';
                        html += '<thead><tr style="background: #f7fafc; border-bottom: 2px solid #e2e8f0;"><th style="padding: 10px; text-align: left;">ファイル名</th><th style="padding: 10px; text-align: right;">サイズ</th><th style="padding: 10px; text-align: center;">操作</th></tr></thead>';
                        html += '<tbody>';
                        data.files.forEach(file => {
                            html += `<tr style="border-bottom: 1px solid #e2e8f0;">`;
                            html += `<td style="padding: 10px;">${file.name}</td>`;
                            html += `<td style="padding: 10px; text-align: right;">${file.size} bytes</td>`;
                            html += `<td style="padding: 10px; text-align: center;">`;
                            html += `<button class="btn btn-primary" style="padding: 5px 15px; font-size: 12px;" onclick="loadFile('${file.name}')">開く</button> `;
                            html += `<button class="btn btn-danger" style="padding: 5px 15px; font-size: 12px;" onclick="deleteFile('${file.name}')">削除</button>`;
                            html += `</td></tr>`;
                        });
                        html += '</tbody></table>';
                    } else {
                        html += '<p style="text-align: center; padding: 40px; color: #718096;">アップロードされたファイルがありません</p>';
                    }
                    html += '</div>';
                    document.getElementById('fileListContent').innerHTML = html;
                    document.getElementById('fileListModal').style.display = 'block';
                } else {
                    showStatus('エラー: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        }
        
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
            const modals = ['structureModal', 'searchModal', 'uploadModal', 'fileListModal'];
            modals.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (event.target == modal) {
                    modal.style.display = 'none';
                }
            });
        }
        
        // HTML構文チェック
        async function validateHTML() {
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
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """メインページ"""
    try:
        filename = None
        html_content = ""
        file_size = 0
        links_count = 0
        images_count = 0
        scripts_count = 0
        
        if html_editor is not None and html_file_path is not None:
            try:
                # HTMLファイルの内容を取得
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 構造情報を取得
                info = html_editor.get_structure_info()
                
                # ファイルサイズを取得
                file_size = os.path.getsize(html_file_path)
                filename = Path(html_file_path).name
                links_count = info['links_count']
                images_count = info['images_count']
                scripts_count = info['scripts_count']
            except Exception as e:
                # ファイル読み込みエラーは無視して、空のエディタを表示
                print(f"警告: ファイル読み込みエラー: {e}")
        
        # テンプレート変数を安全に準備
        # filenameはdata属性として渡すため、エスケープのみ必要
        safe_filename = filename or ''
        
        return render_template_string(
            EDITOR_TEMPLATE,
            filename=safe_filename,
            has_content=bool(html_content and html_content.strip()),
            file_size=file_size or 0,
            links_count=links_count or 0,
            images_count=images_count or 0,
            scripts_count=scripts_count or 0
        )
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"エラー詳細: {error_details}")
        # デバッグモードで詳細なエラーを返す
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


@app.route('/save', methods=['POST'])
def save():
    """ファイルを保存"""
    try:
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        data = request.json
        content = data.get('content', '')
        
        # ファイルに保存
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # HTMLEditorを再読み込み
        global html_editor
        html_editor = HTMLEditor(str(html_file_path))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/content')
def content():
    """HTMLコンテンツを取得"""
    try:
        if html_file_path is None or not html_file_path.exists():
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
        if html_file_path is None:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'}), 400
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # HTMLEditorを再読み込み
        global html_editor
        html_editor = HTMLEditor(str(html_file_path))
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/structure')
def structure():
    """構造情報を取得"""
    try:
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
        
        # グローバル変数を更新
        global html_editor, html_file_path
        html_file_path = file_path
        html_editor = HTMLEditor(str(file_path))
        
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
        
        # グローバル変数を更新
        global html_editor, html_file_path
        html_file_path = file_path
        html_editor = HTMLEditor(str(file_path))
        
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
        
        # 現在開いているファイルを削除する場合は、エディタをクリア
        global html_editor, html_file_path
        if html_file_path and html_file_path == file_path:
            html_editor = None
            html_file_path = None
        
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
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'error': 'コンテンツが空です'})
        
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
    default_port = int(os.environ.get('PORT', 5000))
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
        if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DYNO'):
            host = '0.0.0.0'
        
        app.run(host=host, port=args.port, debug=args.debug)
    
    except KeyboardInterrupt:
        print("\n\nプログラムを終了します。")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

