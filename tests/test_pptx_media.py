"""Tests for any2txt.media.pptx."""

from pathlib import Path

from any2txt.media.pptx import is_pptx


def test_is_pptx_known_extensions() -> None:
    """The pptx extension is recognized (case-insensitive)."""
    assert is_pptx(Path('a.pptx'))
    assert is_pptx(Path('a.PPTX'))
    assert is_pptx(Path('a.Pptx'))


def test_is_pptx_rejects_other_extensions() -> None:
    """Non-pptx extensions are rejected."""
    assert not is_pptx(Path('a.txt'))
    assert not is_pptx(Path('a.ppt'))
    assert not is_pptx(Path('a'))
    assert not is_pptx(Path('a.pptx.txt'))
