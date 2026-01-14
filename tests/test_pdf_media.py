"""Tests for any2txt.media.pdf."""

from pathlib import Path

from any2txt.media.pdf import is_pdf


def test_is_pdf_known_extensions() -> None:
    """The pdf extension is recognized (case-insensitive)."""
    assert is_pdf(Path('a.pdf'))
    assert is_pdf(Path('a.PDF'))
    assert is_pdf(Path('a.Pdf'))


def test_is_pdf_rejects_other_extensions() -> None:
    """Non-pdf extensions are rejected."""
    assert not is_pdf(Path('a.txt'))
    assert not is_pdf(Path('a.docx'))
    assert not is_pdf(Path('a'))
    assert not is_pdf(Path('a.pdf.txt'))
