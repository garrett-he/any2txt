"""docx to Markdown conversion with mammoth.

mammoth turns the document into semantic HTML (headings, lists,
tables, links, emphasis); the rendering to Markdown lives in
:mod:`any2txt.formats.markdown`. Images are written to an asset
directory next to the output file instead of base64 data URIs; OLE
embedded objects cannot be located inside the document flow, so they
are extracted to the same directory and listed in an appendix section.
"""

import io
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO, Protocol

import mammoth
from mammoth import docx as mammoth_docx

from any2txt.assets import AssetSink
from any2txt.formats.markdown import html_to_markdown
from any2txt.zipguard import guard_zip

_CONTENT_TYPE_EXTENSIONS = {
    'image/bmp': 'bmp',
    'image/gif': 'gif',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/svg+xml': 'svg',
    'image/tiff': 'tiff',
    'image/webp': 'webp',
    'image/x-emf': 'emf',
    'image/x-wmf': 'wmf',
}


def _ensure_wps_style_compat() -> None:
    """Teach mammoth to tolerate WPS styles lacking the w:type attribute.

    WPS writes ``<w:style>`` elements without the required ``w:type``
    attribute, which crashes mammoth's styles reader with a KeyError.
    Such styles are treated as paragraph styles (the dominant case) by
    filling the attribute before mammoth reads it.
    """
    original = mammoth_docx.read_styles_xml_element

    def tolerant_read_styles_xml_element(element: Any) -> Any:
        for child in getattr(element, 'children', []):
            if getattr(child, 'name', None) == 'w:style':
                attributes = getattr(child, 'attributes', None)
                if attributes is not None:
                    attributes.setdefault('w:type', 'paragraph')
        return original(element)

    mammoth_docx.read_styles_xml_element = tolerant_read_styles_xml_element
    mammoth_docx.styles_xml.read_styles_xml_element = tolerant_read_styles_xml_element


_ensure_wps_style_compat()


class _MammothImage(Protocol):
    """The subset of the mammoth image object used by the converter."""

    content_type: str

    def open(self) -> BinaryIO:
        """Open the image data stream."""
        ...


def _extension_for(content_type: str) -> str:
    """Map an image content type to a file extension."""
    return _CONTENT_TYPE_EXTENSIONS.get(content_type.split(';')[0].strip().lower(), 'bin')


def _image_handler(sink: AssetSink, counter: list[int]) -> Callable[[_MammothImage], dict[str, str]]:
    """Build a mammoth image converter that hands images to the sink."""

    def convert_image(image: _MammothImage) -> dict[str, str]:
        extension = _extension_for(image.content_type)
        counter[0] += 1
        name = f'image{counter[0]}.{extension}'
        with image.open() as data:
            url = sink.put(name, data.read(), image.content_type)
        return {'src': url or ''}

    return convert_image


def _extract_embeddings(source: Path, sink: AssetSink) -> list[tuple[str, str]]:
    """Hand OLE embedded objects to the sink; return (name, url) pairs."""
    assets: list[tuple[str, str]] = []
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            basename = Path(info.filename).name
            if not info.filename.startswith('word/embeddings/') or not basename:
                continue
            url = sink.put(basename, archive.read(info), 'application/octet-stream')
            if url is not None:
                assets.append((basename, url))
    return assets


_DRAWING_OPEN = '<w:drawing>'
_DRAWING_CLOSE = '</w:drawing>'
_TXBX_OPEN = '<w:txbxContent>'
_TXBX_CLOSE = '</w:txbxContent>'


def _find_drawing_end(xml: str, start: int) -> int:
    """Return the index past the drawing opening at start, handling nesting."""
    depth = 0
    pos = start
    while pos < len(xml):
        open_at = xml.find(_DRAWING_OPEN, pos)
        close_at = xml.find(_DRAWING_CLOSE, pos)
        if close_at == -1:
            return -1
        if open_at != -1 and open_at < close_at:
            depth += 1
            pos = open_at + len(_DRAWING_OPEN)
        else:
            depth -= 1
            pos = close_at + len(_DRAWING_CLOSE)
            if depth == 0:
                return pos
    return -1


def _unwrap_textboxes_once(xml: str) -> tuple[str, bool]:
    """Replace every textbox drawing with its txbxContent paragraphs."""
    result: list[str] = []
    replaced = False
    pos = 0
    while pos < len(xml):
        start = xml.find(_DRAWING_OPEN, pos)
        if start == -1:
            result.append(xml[pos:])
            break
        end = _find_drawing_end(xml, start)
        if end == -1:
            result.append(xml[pos:])
            break
        segment = xml[start:end]
        open_at = segment.find(_TXBX_OPEN)
        close_at = segment.rfind(_TXBX_CLOSE)
        if open_at == -1 or close_at == -1:
            result.append(xml[pos:end])
            pos = end
            continue
        inner = segment[open_at + len(_TXBX_OPEN) : close_at]
        result.append(xml[pos:start])
        if inner.lstrip().startswith('<w:p'):
            # close the surrounding run/paragraph, splice the paragraphs,
            # then reopen so the remaining XML stays well-formed
            result.append('</w:r></w:p>')
            result.append(inner)
            result.append('<w:p><w:r>')
        else:
            result.append(f'<w:p><w:r>{inner}</w:r></w:p>')
        replaced = True
        pos = end
    return ''.join(result), replaced


def _unwrap_textboxes(xml: str) -> str:
    """Hoist textbox content so mammoth can see its runs and pictures.

    mammoth ignores ``wps:txbx`` textboxes entirely, losing both the
    text and any pictures anchored inside them (common in WPS-exported
    documents). Nested textboxes are unwrapped repeatedly.
    """
    for _ in range(8):
        if _TXBX_OPEN not in xml:
            return xml
        unwrapped, replaced = _unwrap_textboxes_once(xml)
        if not replaced:
            return xml
        xml = unwrapped
    return xml


def _open_for_conversion(source: Path) -> BinaryIO:
    """Open a docx package with textbox content hoisted for mammoth."""
    with zipfile.ZipFile(source) as archive:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as copy:
            for info in archive.infolist():
                data = archive.read(info.filename)
                if info.filename == 'word/document.xml':
                    data = _unwrap_textboxes(data.decode('utf-8')).encode('utf-8')
                copy.writestr(info.filename, data)
        buffer.seek(0)
        return buffer


def _append_attachments(markdown: str, attachments: list[tuple[str, str]]) -> str:
    """Append an appendix section linking the extracted embedded objects."""
    lines = ['## 附件', '']
    lines += [f'- [{name}]({url})' for name, url in attachments]
    return markdown.rstrip('\n') + '\n\n' + '\n'.join(lines) + '\n'


def convert_docx(source: Path, sink: AssetSink) -> str:
    """Convert a docx file to Markdown.

    Images and embedded objects are handed to the sink, which decides
    whether they become files, data URIs, or nothing at all. Returns an
    empty string when the document has no content.
    """
    guard_zip(source)
    counter = [0]
    with _open_for_conversion(source) as stream:
        result = mammoth.convert_to_html(
            stream, convert_image=mammoth.images.img_element(_image_handler(sink, counter))
        )
    markdown = html_to_markdown(result.value)
    attachments = _extract_embeddings(source, sink)
    if attachments:
        markdown = _append_attachments(markdown, attachments)
    return markdown.strip('\n')
