"""Tests for any2txt version information."""

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import any2txt


def test_version_is_string() -> None:
    """Verify that __version__ is defined and is a string."""
    assert hasattr(any2txt, '__version__')
    assert isinstance(any2txt.__version__, str)


def test_version_format() -> None:
    """Verify that __version__ follows semantic versioning format."""
    version: str = any2txt.__version__
    parts = version.split('.')
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])


def test_version_fallback_on_package_not_found() -> None:
    """Verify that __version__ falls back to 'unknown' when package metadata is missing."""
    import importlib

    with patch('importlib.metadata.version', side_effect=PackageNotFoundError):
        importlib.reload(any2txt)
    assert any2txt.__version__ == 'unknown'

    importlib.reload(any2txt)
