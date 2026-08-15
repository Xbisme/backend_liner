"""JWT signing-key length is enforced (BE-004 US2, FR-010/SC-003)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.checks import check_jwt_signing_key, signing_key_too_short

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_signing_key_too_short_helper() -> None:
    assert signing_key_too_short("short", 32) is True
    assert signing_key_too_short("x" * 32, 32) is False


def test_check_flags_short_key_when_not_debug(settings: Any) -> None:
    settings.DEBUG = False
    settings.SECRET_KEY = "short"
    settings.JWT_MIN_SECRET_BYTES = 32
    errors = check_jwt_signing_key(None)
    assert [e.id for e in errors] == ["core.E001"]


def test_check_passes_with_long_key(settings: Any) -> None:
    settings.DEBUG = False
    settings.SECRET_KEY = "x" * 32
    settings.JWT_MIN_SECRET_BYTES = 32
    assert check_jwt_signing_key(None) == []


def test_check_skipped_in_debug(settings: Any) -> None:
    settings.DEBUG = True
    settings.SECRET_KEY = "short"
    settings.JWT_MIN_SECRET_BYTES = 32
    assert check_jwt_signing_key(None) == []


def test_production_boot_fails_fast_with_short_key() -> None:
    """Importing production settings with a short key aborts startup (SC-003)."""
    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
    env["DJANGO_SECRET_KEY"] = "short"
    proc = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "SECRET_KEY" in (proc.stderr + proc.stdout)
