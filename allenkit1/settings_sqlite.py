from .settings import *

# Use a local SQLite database for portable backup snapshots.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "backup.sqlite3",
    }
}
