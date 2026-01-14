"""Tests for any2txt.media.html."""

from pathlib import Path

from any2txt.media.html import is_html


def test_is_html_known_extensions() -> None:
    """Common HTML extensions are recognized (case-insensitive)."""
    assert is_html(Path('a.html'))
    assert is_html(Path('a.htm'))
    assert is_html(Path('a.HTML'))
    assert is_html(Path('a.Htm'))


def test_is_html_rejects_other_extensions() -> None:
    """Non-HTML extensions are rejected."""
    assert not is_html(Path('a.txt'))
    assert not is_html(Path('a.md'))
    assert not is_html(Path('a'))
    assert not is_html(Path('a.html.txt'))
