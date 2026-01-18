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
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# フロントエンドの静的ファイルを配信
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'

if FRONTEND_DIST_DIR.exists():
    urlpatterns += [
        re_path(r'^assets/(?P<path>.*)$', serve, {
            'document_root': FRONTEND_DIST_DIR / 'assets',
        }),
        # ロゴ画像などのルートレベルの静的ファイルを配信
        re_path(r'^(?P<path>logo\.png|favicon\.ico)$', serve, {
            'document_root': FRONTEND_DIST_DIR,
        }),
    ]
