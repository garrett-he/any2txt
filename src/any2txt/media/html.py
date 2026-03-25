"""HTML validation, decoding, and local-asset extraction.

Detection is extension-based (case-insensitive). Rendering to Markdown
is handled by the shared HTML-to-Markdown renderer in
:mod:`any2txt.formats.markdown`; images referenced by local paths are
handed to the conversion's asset sink, which decides whether they become
files, data URIs, or nothing at all.
"""

import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup

from any2txt.assets import AssetSink

HTML_EXTENSIONS = frozenset({'.htm', '.html'})

# src="..." values that do not point at a local file.
_REMOTE_SRC_PATTERN = re.compile(r'^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)')
_CHARSET_PATTERN = re.compile(rb"""charset\s*=\s*["']?([\w.-]+)""", re.IGNORECASE)


def is_html(path: Path) -> bool:
    """Return True if the path has an HTML file extension (case-insensitive)."""
    return path.suffix.lower() in HTML_EXTENSIONS


def read_html(source: Path) -> str:
    """Decode an HTML file, falling back to the declared charset and GB18030.

    UTF-8 with an optional BOM is tried first; a declared charset in the
    first 4 KiB comes next, then GB18030 (common for legacy Chinese
    pages), and finally lossy UTF-8 so conversion never fails on encoding.
    """
    raw = source.read_bytes()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        pass
    match = _CHARSET_PATTERN.search(raw[:4096])
    if match is not None:
        try:
            return raw.decode(match.group(1).decode('ascii'))
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return raw.decode('gb18030')
    except UnicodeDecodeError:
        return raw.decode('utf-8', errors='replace')


def _is_local_reference(src: str) -> bool:
    """Return True if an img src looks like a local filesystem path."""
    return not _REMOTE_SRC_PATTERN.match(src)


def _candidate_path(src: str, source: Path) -> Path:
    """Resolve an img src against the HTML file's directory."""
    local = unquote(src.replace('\\', '/'))
    candidate = Path(local)
    return candidate if candidate.is_absolute() else source.parent / candidate


def _unique_name(basename: str, taken: set[str]) -> str:
    """Return an asset filename derived from basename that is unused in this run."""
    if basename not in taken:
        taken.add(basename)
        return basename
    stem, dot, suffix = basename.rpartition('.')
    prefix = f'{stem}_' if dot else f'{basename}_'
    extension = f'.{suffix}' if dot else ''
    index = 0
    name = basename
    while name in taken:
        index += 1
        name = f'{prefix}{index}{extension}'
    taken.add(name)
    return name


def rewrite_local_images(html: str, source: Path, sink: AssetSink) -> str:
    """Hand images referenced by local paths to the sink and rewrite their src.

    Relative paths are resolved against the HTML file's directory and
    Windows-style separators are accepted. Remote URLs and data URIs are
    left untouched, as are references to files that do not exist. When
    the sink drops an asset the ``<img>`` element is removed so no
    dangling reference survives. Returns the rewritten HTML.
    """
    soup = BeautifulSoup(html, 'html.parser')
    taken: set[str] = set()
    for img in soup.find_all('img'):
        src = img.get('src')
        if not isinstance(src, str) or not _is_local_reference(src):
            continue
        candidate = _candidate_path(src, source)
        if not candidate.is_file():
            continue
        name = _unique_name(candidate.name.replace(' ', '_'), taken)
        mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        url = sink.put(name, candidate.read_bytes(), mime)
        if url is None:
            img.decompose()
        else:
            img['src'] = url
    return str(soup)
