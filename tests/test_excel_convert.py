"""Tests for any2txt.excel conversion.

Fixtures are built with openpyxl itself, so no real Excel files,
network, or external tools are required.
"""

from pathlib import Path

from openpyxl import Workbook  # pyrefly: ignore

from any2txt.excel import convert_excel


def build_workbook(path: Path) -> Path:
    """Create a workbook with a data sheet and an empty sheet."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = 'Data'
    sheet.append(['Name', 'Score'])
    sheet.append(['Alice', 90])
    sheet.append(['Bob|2', 95.5])
    workbook.create_sheet('Blank')
    workbook.save(str(path))
    return path


def test_convert_sheets_as_headings_and_tables(tmp_path: Path) -> None:
    """Each non-empty sheet becomes a h2 section with a pipe table."""
    source = build_workbook(tmp_path / 'book.xlsx')
    markdown = convert_excel(source)
    assert '## Data' in markdown
    assert '| Name | Score |' in markdown
    assert '| --- | --- |' in markdown
    assert '| Alice | 90 |' in markdown


def test_convert_escapes_pipes_in_cells(tmp_path: Path) -> None:
    """Pipe characters inside cells do not break the table."""
    source = build_workbook(tmp_path / 'book.xlsx')
    markdown = convert_excel(source)
    assert r'Bob\|2' in markdown


def test_convert_skips_empty_sheets(tmp_path: Path) -> None:
    """Sheets without content do not produce sections."""
    source = build_workbook(tmp_path / 'book.xlsx')
    markdown = convert_excel(source)
    assert '## Blank' not in markdown


def test_convert_empty_workbook(tmp_path: Path) -> None:
    """A workbook without any content converts to an empty string."""
    source = tmp_path / 'empty.xlsx'
    Workbook().save(str(source))
    assert convert_excel(source) == ''
