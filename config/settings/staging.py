"""Staging settings — production-like, relaxed for QA."""

from .base import env
from .production import *  # noqa: F401,F403

DEBUG = env.bool("DJANGO_DEBUG", default=False)
