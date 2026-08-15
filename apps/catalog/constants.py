"""Static catalog constants (Constitution IV/VI).

Cache-key namespace, Jamendo request parameter names/values, and the Creative
Commons license URL → label lookup. Tunables (TTLs, page sizes, base URL, timeout,
audioformat, curated genres) live in settings/env, not here.
"""

from __future__ import annotations

# Cache-key namespace — bump the version suffix to invalidate all catalog caches.
CACHE_NAMESPACE = "catalog:v1"

# Jamendo query behaviour. NOTE: the trending ``order`` is env-driven
# (settings.JAMENDO_TRENDING_ORDER) — Jamendo's time-windowed popularity_* orders
# return empty on the free tier, so it must be tunable without a code change.
JAMENDO_TRACK_INCLUDE = "musicinfo+licenses"

# Map a Creative Commons deed URL (Jamendo ``license_ccurl``) to its human label.
# Order matters: more specific licenses first (``by-nc-sa`` before ``by-nc``/``by``).
CC_LICENSE_LABELS: tuple[tuple[str, str], ...] = (
    ("by-nc-sa", "CC BY-NC-SA"),
    ("by-nc-nd", "CC BY-NC-ND"),
    ("by-nc", "CC BY-NC"),
    ("by-sa", "CC BY-SA"),
    ("by-nd", "CC BY-ND"),
    ("by", "CC BY"),
)


def license_label(ccurl: str | None, fallback: str = "") -> str:
    """Derive a CC label from a Jamendo ``license_ccurl``.

    Returns the matched label, else ``fallback`` (raw license string), else ``""``.
    The raw URL is never returned (Principle IV — no upstream shape leakage).
    """
    if ccurl:
        needle = ccurl.lower()
        for token, label in CC_LICENSE_LABELS:
            if f"/{token}/" in needle:
                return label
    return fallback or ""
