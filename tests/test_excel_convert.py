"""Tests for any2txt.excel conversion.

Fixtures are built with openpyxl itself, so no real Excel files,
network, or external tools are required.
"""

import base64
import io
from pathlib import Path

from openpyxl import Workbook  # pyrefly: ignore
from openpyxl.drawing.image import Image as XlsxImage  # pyrefly: ignore

from any2txt.excel import convert_excel

PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)


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


def convert_fixture(tmp_path: Path) -> str:
    """Build a workbook fixture, convert it, and return the Markdown."""
    source = build_workbook(tmp_path / 'book.xlsx')
    return convert_excel(source, tmp_path / 'book.md')


def test_convert_sheets_as_headings_and_tables(tmp_path: Path) -> None:
    """Each non-empty sheet becomes a h2 section with a pipe table."""
    markdown = convert_fixture(tmp_path)
    assert '## Data' in markdown
    assert '| Name | Score |' in markdown
    assert '| --- | --- |' in markdown
    assert '| Alice | 90 |' in markdown


def test_convert_escapes_pipes_in_cells(tmp_path: Path) -> None:
    """Pipe characters inside cells do not break the table."""
    markdown = convert_fixture(tmp_path)
    assert r'Bob\|2' in markdown


def test_convert_skips_empty_sheets(tmp_path: Path) -> None:
    """Sheets without content do not produce sections."""
    markdown = convert_fixture(tmp_path)
    assert '## Blank' not in markdown


def test_convert_empty_workbook(tmp_path: Path) -> None:
    """A workbook without any content converts to an empty string."""
    source = tmp_path / 'empty.xlsx'
    Workbook().save(str(source))
    assert convert_excel(source, tmp_path / 'empty.md') == ''


def test_convert_fills_merged_cells(tmp_path: Path) -> None:
    """Merged ranges repeat their top-left value on every row."""
    source = tmp_path / 'merged.xlsx'
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(['Category', 'Item'])
    sheet.append([None, 'one'])
    sheet.append([None, 'two'])
    sheet.merge_cells('A2:A3')
    sheet['A2'] = 'Group'
    workbook.save(str(source))
    markdown = convert_excel(source, tmp_path / 'merged.md')
    assert '| Group | one |' in markdown
    assert '| Group | two |' in markdown


def test_convert_images_extracts_to_assets(tmp_path: Path) -> None:
    """Anchored pictures are extracted and referenced in their cell."""
    source = tmp_path / 'images.xlsx'
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(['Name', 'Picture'])
    sheet.append(['row', None])
    image = XlsxImage(io.BytesIO(PNG_1X1))
    sheet.add_image(image, 'B2')
    workbook.save(str(source))
    markdown = convert_excel(source, tmp_path / 'images.md')
    assets = tmp_path / 'images_files'
    pictures = list(assets.glob('image*.png'))
    assert len(pictures) == 1
    assert pictures[0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert f'images_files/{pictures[0].name}' in markdown
    assert '![image1.png](images_files/image1.png)' in markdown
