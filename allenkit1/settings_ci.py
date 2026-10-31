"""CI-friendly settings: in-memory SQLite, no external services required."""

from .settings import *  # noqa: F403

DEBUG = True
SECRET_KEY = "ci-test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Avoid Redis/Celery side effects during unit tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
