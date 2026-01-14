"""Tests for any2txt.media.excel."""

from pathlib import Path

from any2txt.media.excel import is_excel


def test_is_excel_known_extensions() -> None:
    """Common excel extensions are recognized (case-insensitive)."""
    assert is_excel(Path('a.xlsx'))
    assert is_excel(Path('a.xlsm'))
    assert is_excel(Path('a.XLSX'))
    assert is_excel(Path('a.Xlsm'))


def test_is_excel_rejects_other_extensions() -> None:
    """Non-excel extensions are rejected."""
    assert not is_excel(Path('a.txt'))
    assert not is_excel(Path('a.xls'))
    assert not is_excel(Path('a'))
    assert not is_excel(Path('a.xlsx.txt'))
