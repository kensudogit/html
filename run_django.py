#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Djangoアプリケーションの起動スクリプト
"""
import os
import sys
from pathlib import Path

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'html_editor.settings')
    
    # Railway環境でのポート設定
    port = os.environ.get('PORT', '5000')
    host = '0.0.0.0'
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Django開発サーバーを起動
    execute_from_command_line(['manage.py', 'runserver', f'{host}:{port}'])
