"""
URL configuration for html_editor project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('editor.urls')),
]

# 静的ファイルとメディアファイルの配信
# 本番環境でも静的ファイルを配信（Railway環境用）
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'

# 静的ファイルの配信（DEBUG=Falseでも動作するように）
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # 本番環境でも静的ファイルを配信
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

# フロントエンドの静的ファイルを配信（本番環境でも動作）
# 常にURLパターンを追加（存在チェックはビューで行う）
urlpatterns += [
    re_path(r'^assets/(?P<path>.*)$', serve, {
        'document_root': FRONTEND_DIST_DIR / 'assets',
    }),
    # ロゴ画像などのルートレベルの静的ファイルを配信
    re_path(r'^(?P<path>logo\.png|favicon\.ico)$', serve, {
        'document_root': FRONTEND_DIST_DIR,
    }),
]
