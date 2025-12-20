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
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            position: relative;
            height: 600px;
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
            width: 8px;
            background: #cbd5e0;
            cursor: col-resize;
            position: relative;
            flex-shrink: 0;
            z-index: 10;
            transition: background 0.2s;
        }
        .resizer:hover {
            background: #667eea;
        }
        .resizer::before {
            content: '';
            position: absolute;
            left: 50%;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #667eea;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.2s;
        }
        .resizer:hover::before {
            opacity: 1;
        }
        .resizer.resizing {
            background: #667eea;
        }
        .resizer.resizing::before {
            opacity: 1;
        }
        .editor-panel {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
            flex: 1;
            min-width: 200px;
            display: flex;
            flex-direction: column;
        }
        .editor-panel:first-child {
            border-top-right-radius: 0;
            border-bottom-right-radius: 0;
        }
        .editor-panel:last-child {
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }
        .panel-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px 20px;
            border-bottom: 2px solid #5568d3;
            font-weight: 600;
            color: white;
            font-size: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .panel-header span {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }
        #previewPanel .panel-header {
            background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
            border-bottom: 3px solid #2f855a;
            box-shadow: 0 4px 6px rgba(72, 187, 120, 0.2);
        }
        #previewPanel .panel-header span {
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
            font-size: 17px;
        }
        .editor-wrapper {
            position: relative;
            width: 100%;
            height: 600px;
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
            position: relative;
            z-index: 1;
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
            border: 3px solid #e2e8f0;
            border-top: none;
            background: #ffffff;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.03), 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            position: relative;
        }
        .preview:hover {
            border-color: #cbd5e0;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.15);
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
        /* リモコン盤スタイル */
        #remoteControl {
            position: fixed;
            z-index: 10000;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            min-width: 300px;
            max-width: 90vw;
            transition: all 0.3s ease;
            user-select: none;
        }
        #remoteControl.collapsed {
            min-width: auto;
            width: auto;
        }
        #remoteControl.collapsed .remote-control-content {
            display: none;
        }
        #remoteControl.collapsed .remote-control-header {
            border-radius: 12px;
        }
        .remote-control-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 12px 16px;
            border-radius: 12px 12px 0 0;
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
            gap: 8px;
            font-size: 14px;
        }
        .remote-control-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .remote-control-toggle:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.1);
        }
        .remote-control-content {
            background: white;
            padding: 16px;
            border-radius: 0 0 12px 12px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .remote-control-section {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .remote-control-section-title {
            font-size: 12px;
            font-weight: 600;
            color: #4a5568;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .remote-control-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .remote-control-buttons .btn {
            flex: 1;
            min-width: 120px;
            font-size: 13px;
            padding: 8px 12px;
        }
        .remote-control-search {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .remote-control-search input {
            flex: 1;
            padding: 8px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 13px;
        }
        .remote-control-search .btn {
            flex: 0 0 auto;
            min-width: auto;
            padding: 8px 16px;
        }
        .remote-control-nav-buttons {
            display: flex;
            gap: 6px;
        }
        .remote-control-nav-buttons .btn {
            flex: 1;
            min-width: auto;
            padding: 8px 12px;
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
    
    <!-- リモコン盤 -->
    <div id="remoteControl">
        <div class="remote-control-header" id="remoteControlHeader">
            <div class="remote-control-title">🎮 リモコン盤</div>
            <button class="remote-control-toggle" id="remoteControlToggle" onclick="toggleRemoteControl()" title="開閉">▼</button>
        </div>
        <div class="remote-control-content" id="remoteControlContent">
            <!-- ファイル操作セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">ファイル操作</div>
                <div class="remote-control-buttons">
                    <button class="btn btn-primary" onclick="showUploadModal()" id="uploadBtnMain" style="font-weight: 600; background: #667eea; border: 2px solid #5568d3; color: white;">
                        📤 アップロード
                    </button>
                    <button class="btn btn-success" onclick="downloadFile()" id="downloadBtn" {% if not filename %}disabled{% endif %} style="font-weight: 600; background: #48bb78; border-color: #38a169; color: white;">
                        ⬇️ ダウンロード
                    </button>
                    <button class="btn btn-info" onclick="showFileList()" id="fileListBtn">📁 ファイル一覧</button>
                </div>
            </div>
            
            <!-- 編集操作セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">編集操作</div>
                <div class="remote-control-buttons">
                    <button class="btn btn-primary" onclick="saveFile()" id="saveBtn" {% if not filename %}disabled{% endif %}>💾 保存</button>
                    <button class="btn btn-success" onclick="reloadFile()" id="reloadBtn" {% if not filename %}disabled{% endif %}>🔄 再読み込み</button>
                    <button class="btn btn-danger" onclick="clearEditor()" id="clearBtn">🗑️ クリア</button>
                    <button class="btn btn-info" onclick="showStructure()" id="structureBtn" {% if not filename %}disabled{% endif %}>📊 構造情報</button>
                    <button class="btn btn-warning" onclick="validateHTML()" id="validateBtn" {% if not filename %}disabled{% endif %}>⚠️ 構文チェック</button>
                    <button class="btn btn-info" onclick="showSearch()" id="searchBtn" {% if not filename %}disabled{% endif %}>🔍 検索・置換</button>
                    <button class="btn btn-info" onclick="showDesignExport()" id="exportDesignBtn" {% if not filename %}disabled{% endif %} title="プレビューのDOMと主要CSS(Computed Style)をJSON/CSVで出力して比較に使います">📤 デザイン出力</button>
                </div>
            </div>
            
            <!-- 要素検索セクション -->
            <div class="remote-control-section">
                <div class="remote-control-section-title">要素検索</div>
                <div class="remote-control-search">
                    <input type="text" id="searchBox" placeholder="ID、クラス、タグ、テキストで検索..." onkeypress="if(event.key==='Enter') searchElement()" {% if not filename %}disabled{% endif %}>
                    <button class="btn btn-info" onclick="searchElement()" id="searchElementBtn" {% if not filename %}disabled{% endif %}>検索</button>
                </div>
                <div class="remote-control-nav-buttons">
                    <button class="btn btn-info" onclick="highlightPrevious()" id="prevMatchBtn" style="display: none;" title="前の検索結果へ">▲ 前へ</button>
                    <button class="btn btn-info" onclick="highlightNext()" id="nextMatchBtn" style="display: none;" title="次の検索結果へ">次へ ▼</button>
                </div>
                <span id="matchCounter" style="display: none; font-size: 12px; color: #666; text-align: center;"></span>
            </div>
        </div>
    </div>
    
    <div class="container">
        
        <div id="errorPanel" style="display: none; background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 15px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; color: #856404;">⚠️ 構文エラー・警告</h3>
                <button onclick="document.getElementById('errorPanel').style.display='none'" style="background: #ffc107; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">閉じる</button>
            </div>
            <div id="errorList"></div>
        </div>
        
        <div id="status" class="status"></div>
        
        <div class="editor-container">
            <div class="editor-panel" id="editorPanel">
                <div class="panel-header"><span>📄 HTMLソース</span></div>
                <div class="editor-wrapper">
                    <textarea id="htmlEditor" class="editor" spellcheck="false" data-filename="{{ filename|e }}" data-has-content="{% if has_content %}true{% else %}false{% endif %}"></textarea>
                    <div id="editorHighlight" class="editor-highlight"></div>
                </div>
            </div>
            <div class="resizer" id="resizer"></div>
            <div class="editor-panel" id="previewPanel">
                <div class="panel-header">
                    <span>👁️ プレビュー</span>
                    <button class="btn btn-success" onclick="downloadPreview()" id="downloadPreviewBtn" style="font-size: 12px; padding: 6px 12px; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; font-weight: 600;" title="プレビューをHTMLファイルとしてダウンロード" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
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
            
            // リモコン盤の初期化
            initRemoteControl();
            
            // リサイザーの実装
            const resizer = document.getElementById('resizer');
            const editorPanel = document.getElementById('editorPanel');
            const previewPanel = document.getElementById('previewPanel');
            const editorContainer = document.querySelector('.editor-container');
            
            if (resizer && editorPanel && previewPanel && editorContainer) {
                let isResizing = false;
                let startX = 0;
                let startEditorWidth = 0;
                
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
                    const minWidth = 200;
                    const maxWidth = containerWidth - resizerWidth - minWidth;
                    
                    if (newEditorWidth >= minWidth && newEditorWidth <= maxWidth) {
                        editorPanel.style.flex = `0 0 ${newEditorWidth}px`;
                        previewPanel.style.flex = '1 1 auto';
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
            
            // エディタの変更をプレビューに反映
            if (editor && preview) {
                editor.addEventListener('input', function() {
                    updatePreview();
                    // 検索結果がある場合はハイライトを更新
                    if (window.searchMatches && window.searchMatches.length > 0) {
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
                    }, 150);
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
                function(match, before, middle1, href, middle2, after) {
                    // media属性がある場合は保持
                    const mediaMatch = (before + middle1 + middle2 + after).match(/media=["']([^"']+)["']/i);
                    const mediaAttr = mediaMatch ? ` media="${mediaMatch[1]}"` : '';
                    return `<link rel="stylesheet" href="${href}"${mediaAttr}>`;
                }
            );
            
            // より単純なパターンも処理（属性の順序が異なる場合）
            content = content.replace(
                /<link\s+rel=["']preload["']\s+href=["']([^"']+)["']\s+as=["']style["']\s*[^>]*>/gi,
                function(match, href) {
                    // media属性を抽出
                    const mediaMatch = match.match(/media=["']([^"']+)["']/i);
                    const mediaAttr = mediaMatch ? ` media="${mediaMatch[1]}"` : '';
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
                            if (pathParts.length > 0) {
                                pathParts.pop();
                            }
                        } else if (part !== '.') {
                            pathParts.push(part);
                        }
                    }
                    
                    return window.location.origin + '/' + pathParts.join('/');
                } else if (path.startsWith('./')) {
                    return window.location.origin + basePath + path.substring(2);
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
            const modals = ['structureModal', 'searchModal', 'designExportModal', 'uploadModal', 'fileListModal'];
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

