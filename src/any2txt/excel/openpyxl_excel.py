"""xlsx to Markdown conversion with openpyxl.

Each worksheet becomes a ``## {sheet name}`` section containing the
sheet's grid as a Markdown pipe table, with the first row used as the
table header. Cell line breaks become ``<br>`` and pipes are escaped.
Formula cells are rendered with their last computed value (``data_only``).
Sheets without any content are skipped.
"""

from pathlib import Path

from openpyxl import load_workbook  # pyrefly: ignore
from openpyxl.workbook.workbook import Workbook  # pyrefly: ignore
from openpyxl.worksheet.worksheet import Worksheet  # pyrefly: ignore


def _cell_to_text(value: object) -> str:
    """Render one cell value as single-line table text."""
    if value is None:
        return ''
    return str(value).replace('\r\n', '\n').replace('\n', '<br>').replace('|', '\\|').strip()


def _sheet_to_lines(worksheet: Worksheet) -> list[str]:
    """Render one worksheet's grid as Markdown pipe-table lines."""
    rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    while rows and all(_cell_to_text(value) == '' for value in rows[-1]):
        rows.pop()
    if not rows:
        return []
    width = max(len(row) for row in rows)
    grid = [[_cell_to_text(value) for value in row] + [''] * (width - len(row)) for row in rows]
    lines = [
        '| ' + ' | '.join(grid[0]) + ' |',
        '| ' + ' | '.join(['---'] * width) + ' |',
    ]
    lines += ['| ' + ' | '.join(row) + ' |' for row in grid[1:]]
    return lines


def _sections(workbook: Workbook) -> list[str]:
    """Render every non-empty worksheet as a ``## `` section."""
    sections: list[str] = []
    for worksheet in workbook.worksheets:
        lines = _sheet_to_lines(worksheet)
        if not lines:
            continue
        sections.append('\n'.join([f'## {worksheet.title}', '', *lines]))
    return sections


def convert_excel(source: Path) -> str:
    """Convert an excel file to Markdown, one ``## `` section per sheet.

    Returns an empty string when the workbook has no content at all.
    """
    workbook = load_workbook(source, data_only=True, read_only=True)
    try:
        return '\n\n'.join(_sections(workbook)).strip('\n')
    finally:
        workbook.close()
