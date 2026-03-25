"""Runtime path helpers for packaged builds.

A Nuitka onefile executable keeps its external dependencies in
``lib/site-packages`` and its optional model packages in ``models``,
both next to the executable. These helpers locate those directories
without importing any third-party module, so they are safe to use from
the bootstrap launcher.
"""

import os
import sys
from pathlib import Path

MODELS_ENV = 'ANY2TXT_MODELS'


def is_packaged() -> bool:
    """Return True when running from a compiled (frozen) executable."""
    return '__compiled__' in globals() or bool(getattr(sys, 'frozen', False))


def app_dir() -> Path:
    """Return the directory that holds the executable and its external packages."""
    if sys.argv and sys.argv[0]:
        return Path(sys.argv[0]).resolve().parent
    return Path(sys.executable).resolve().parent


def models_dir() -> Path | None:
    """Return the model directory, or None when running from source.

    ``ANY2TXT_MODELS`` overrides the location in every mode; packaged
    builds fall back to ``models`` next to the executable. Source runs
    keep using the standard Hugging Face cache.
    """
    override = os.environ.get(MODELS_ENV)
    if override:
        return Path(override)
    if not is_packaged():
        return None
    return app_dir() / 'models'
