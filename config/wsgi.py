import os
import sys
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    application = get_wsgi_application()
except Exception as e:
    sys.stderr.write(f"\n\n🔥 WSGI startup error: {repr(e)}\n\n")
    raise
