import os
import sys
from django.core.wsgi import get_wsgi_application

# Set the default settings module for the 'django' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Get the WSGI application
try:
    application = get_wsgi_application()
except Exception as e:
    sys.stderr.write(f"\n\n🔥 WSGI startup error: {repr(e)}\n\n")
    raise

# 👇 This is REQUIRED for Vercel to detect the entry point
app = application  # Vercel looks for 'app' or 'handler'
