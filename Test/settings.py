import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Security & Hosts
# Generate a strong random key for production or load from environment variables
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = False

ALLOWED_HOSTS = [
    "fcerequas.pythonanywhere.com",
    "www.BlushingMoon.org",  # Uncomment if using a custom domain on a paid plan
]

# 2. Static & Media File Locations
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# 3. HTTPS & Cookie Security (recommended once HTTPS is enabled on the Web tab)
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True