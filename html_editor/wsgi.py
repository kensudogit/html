"""
WSGI config for html_editor project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'html_editor.settings')

application = get_wsgi_application()
