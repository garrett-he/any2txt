"""HTML validation.

Detection is extension-based (case-insensitive). Rendering to Markdown
is handled by the shared HTML-to-Markdown renderer in
:mod:`any2txt.formats.markdown`.
"""

from pathlib import Path

HTML_EXTENSIONS = frozenset({'.htm', '.html'})


def is_html(path: Path) -> bool:
    """Return True if the path has an HTML file extension (case-insensitive)."""
    return path.suffix.lower() in HTML_EXTENSIONS
