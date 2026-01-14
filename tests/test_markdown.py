"""Tests for any2txt.formats.markdown."""

from any2txt.formats.markdown import html_to_markdown


def test_headings_use_atx_style() -> None:
    """Headings are rendered as ATX markers."""
    markdown = html_to_markdown('<h1>Title</h1><h2>Sub</h2>')
    assert '# Title' in markdown
    assert '## Sub' in markdown


def test_emphasis_and_links() -> None:
    """Strong, emphasis and anchors keep their Markdown syntax."""
    markdown = html_to_markdown('<p><b>bold</b> and <i>italic</i> <a href="https://x.com">link</a></p>')
    assert '**bold**' in markdown
    assert '*italic*' in markdown
    assert '[link](https://x.com)' in markdown


def test_lists_use_dash_bullets() -> None:
    """Unordered lists use dash bullets."""
    markdown = html_to_markdown('<ul><li>one</li><li>two</li></ul>')
    assert '- one' in markdown
    assert '- two' in markdown


def test_tables_become_pipe_tables() -> None:
    """Tables are rendered as Markdown pipe tables."""
    markdown = html_to_markdown('<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>')
    assert '| A | B |' in markdown
    assert '| --- | --- |' in markdown
    assert '| 1 | 2 |' in markdown


def test_pipes_in_cells_are_escaped() -> None:
    """Pipe characters inside cells do not break the table."""
    markdown = html_to_markdown('<table><tr><td>a|b</td></tr></table>')
    assert r'a\|b' in markdown


def test_empty_html() -> None:
    """Empty input produces an empty string."""
    assert html_to_markdown('') == ''
