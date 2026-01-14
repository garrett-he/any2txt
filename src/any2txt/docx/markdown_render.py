"""HTML to Markdown rendering built on markdownify.

markdownify has no Markdown table support, so this module subclasses
:class:`markdownify.MarkdownConverter` and adds table conversion.
"""

from bs4 import Tag
from markdownify import MarkdownConverter


class TableMarkdownConverter(MarkdownConverter):
    """MarkdownConverter with Markdown table support."""

    def _render_cell(self, cell: Tag) -> str:
        """Render one table cell to a single-line Markdown fragment."""
        rendered = self.process_tag(cell, text='')
        return rendered.strip().replace('\n', ' ').replace('|', '\\|')

    def convert_table(self, el: Tag, text: str, parent_tags: tuple[str, ...] | None = None) -> str:
        """Convert an HTML table to Markdown pipe-table syntax."""
        rows = el.find_all('tr')
        if not rows:
            return text
        grid = [[self._render_cell(cell) for cell in row.find_all(['th', 'td'])] for row in rows]
        grid = [row for row in grid if row]
        if not grid:
            return text
        width = max(len(row) for row in grid)
        padded = [row + [''] * (width - len(row)) for row in grid]
        lines = [
            '| ' + ' | '.join(padded[0]) + ' |',
            '| ' + ' | '.join(['---'] * width) + ' |',
        ]
        lines += ['| ' + ' | '.join(row) + ' |' for row in padded[1:]]
        return '\n' + '\n'.join(lines) + '\n\n'


def html_to_markdown(html: str) -> str:
    """Convert an HTML fragment to Markdown."""
    converter = TableMarkdownConverter(heading_style='ATX', bullets='-')
    return converter.convert(html)
