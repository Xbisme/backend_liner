"""Development settings."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

# A default app key so the local/test suite can exercise the gate.
X_APP_KEY = env("X_APP_KEY", default="dev-app-key")
