"""Tests for any2txt.media.docx."""

from pathlib import Path

from any2txt.media.docx import is_docx


def test_is_docx_known_extensions() -> None:
    """The docx extension is recognized (case-insensitive)."""
    assert is_docx(Path('a.docx'))
    assert is_docx(Path('a.DOCX'))
    assert is_docx(Path('a.Docx'))


def test_is_docx_rejects_other_extensions() -> None:
    """Non-docx extensions are rejected."""
    assert not is_docx(Path('a.txt'))
    assert not is_docx(Path('a.doc'))
    assert not is_docx(Path('a'))
    assert not is_docx(Path('a.docx.txt'))
