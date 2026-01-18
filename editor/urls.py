"""
URL configuration for editor app.
"""
from django.urls import path, re_path
from django.views.static import serve
from django.conf import settings
from pathlib import Path
from . import views

app_name = 'editor'

urlpatterns = [
    # 静的アセット（メインページより前に定義）
    path('assets/<path:filename>', views.serve_assets, name='serve_assets'),
    path('favicon.ico', views.favicon, name='favicon'),
    path('logo.png', views.serve_logo, name='serve_logo'),
    
    # メインページ - Reactアプリケーションを配信
    path('', views.index, name='index'),
    
    # ファイル操作
    path('save', views.save, name='save'),
    path('content', views.content, name='content'),
    path('reload', views.reload, name='reload'),
    path('structure', views.structure, name='structure'),
    path('upload', views.upload, name='upload'),
    path('files', views.files, name='files'),
    path('load/<str:filename>', views.load_file, name='load_file'),
    path('delete/<str:filename>', views.delete_file, name='delete_file'),
    
    # 検索・検証
    path('search', views.search, name='search'),
    path('validate', views.validate, name='validate'),
    
    # 差分分析
    path('diff-analysis', views.diff_analysis, name='diff_analysis'),
    
    # テンプレート関連
    path('gcd-template', views.gcd_template, name='gcd_template'),
    path('template-merge', views.template_merge, name='template_merge'),
    
    # 大学ページ生成
    path('generate-university-pages', views.generate_university_pages, name='generate_university_pages'),
    path('download-university-pages', views.download_university_pages, name='download_university_pages'),
    
    # API endpoints
    path('api/list-directory-files', views.api_list_directory_files, name='api_list_directory_files'),
    path('api/config', views.api_config, name='api_config'),
    path('api/check-directory', views.api_check_directory, name='api_check_directory'),
    path('api/load-comparison-files', views.api_load_comparison_files, name='api_load_comparison_files'),
    path('api/load-file-content', views.api_load_file_content, name='api_load_file_content'),
    path('api/compare-screens', views.api_compare_screens, name='api_compare_screens'),
    path('api/export-comparison-report', views.api_export_comparison_report, name='api_export_comparison_report'),
    path('api/universities', views.api_universities, name='api_universities'),  # GET and POST handled in view
    path('api/page-titles', views.api_page_titles, name='api_page_titles'),
    path('api/university/<int:university_id>/pages', views.api_university_pages, name='api_university_pages'),
    path('api/university/<int:university_id>/page/<int:page_title_id>', views.api_university_page_detail, name='api_university_page_detail'),
    path('api/university/<int:university_id>/config', views.api_university_config, name='api_university_config'),
    path('api/generate-university-page', views.api_generate_university_page, name='api_generate_university_page'),
    path('api/generate-pages-from-yaml', views.api_generate_pages_from_yaml, name='api_generate_pages_from_yaml'),
    path('api/generate-pages-from-yaml-download', views.api_generate_pages_from_yaml_download, name='api_generate_pages_from_yaml_download'),
    
    # SPAルーティング - すべてのパスをindex.htmlにフォールバック
    re_path(r'^(?!api/|admin/|static/|media/).*$', views.index, name='spa_fallback'),
]
