"""WSGI config for RevenueOS project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")

application = get_wsgi_application()
