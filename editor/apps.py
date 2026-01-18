from django.apps import AppConfig
import sqlite3
from pathlib import Path
from django.conf import settings


class EditorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'editor'
    
    def ready(self):
        """アプリケーション起動時にデータベースを初期化"""
        init_database()


def init_database():
    """大学データ管理用のデータベースを初期化"""
    UPLOAD_DIR = Path(settings.MEDIA_ROOT)
    DB_PATH = UPLOAD_DIR / 'university_data.db'
    UNIVERSITY_CONFIG_DIR = UPLOAD_DIR / 'university_configs'
    UNIVERSITY_CONFIG_DIR.mkdir(exist_ok=True, parents=True)
    
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
    ]
    
    for title in default_titles:
        cursor.execute('''
            INSERT OR IGNORE INTO page_titles (title, display_order)
            VALUES (?, ?)
        ''', (title, default_titles.index(title)))
    
    conn.commit()
    conn.close()
