"""docx to Markdown conversion with mammoth.

mammoth turns the document into semantic HTML (headings, lists,
tables, links, emphasis); the rendering to Markdown lives in
:mod:`any2txt.formats.markdown`. Images are written to an asset
directory next to the output file instead of base64 data URIs; OLE
embedded objects cannot be located inside the document flow, so they
are extracted to the same directory and listed in an appendix section.
"""

import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Protocol

import mammoth

from any2txt.formats.markdown import html_to_markdown

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


class _MammothImage(Protocol):
    """The subset of the mammoth image object used by the converter."""

    content_type: str

    def open(self) -> BinaryIO:
        """Open the image data stream."""
        ...


def assets_dir_for(output: Path) -> Path:
    """Return the asset directory that accompanies one output file."""
    return output.parent / f'{output.stem}_files'


def _extension_for(content_type: str) -> str:
    """Map an image content type to a file extension."""
    return _CONTENT_TYPE_EXTENSIONS.get(content_type.split(';')[0].strip().lower(), 'bin')


def _image_handler(assets_dir: Path, counter: list[int]) -> Callable[[_MammothImage], dict[str, str]]:
    """Build a mammoth image converter that writes images into assets_dir."""

    def convert_image(image: _MammothImage) -> dict[str, str]:
        extension = _extension_for(image.content_type)
        counter[0] += 1
        name = f'image{counter[0]}.{extension}'
        assets_dir.mkdir(parents=True, exist_ok=True)
        with image.open() as data:
            (assets_dir / name).write_bytes(data.read())
        return {'src': f'{assets_dir.name}/{name}'}

    return convert_image


def _extract_embeddings(source: Path, assets_dir: Path) -> list[str]:
    """Extract OLE embedded objects from the docx package into assets_dir."""
    names: list[str] = []
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            basename = Path(info.filename).name
            if not info.filename.startswith('word/embeddings/') or not basename:
                continue
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / basename).write_bytes(archive.read(info))
            names.append(basename)
    return names


def _append_attachments(markdown: str, attachments: list[str], assets_dir: Path) -> str:
    """Append an appendix section linking the extracted embedded objects."""
    lines = ['## 附件', '']
    lines += [f'- [{name}]({assets_dir.name}/{name})' for name in attachments]
    return markdown.rstrip('\n') + '\n\n' + '\n'.join(lines) + '\n'


def convert_docx(source: Path, output: Path) -> str:
    """Convert a docx file to Markdown.

    Images and embedded objects are extracted into ``{output.stem}_files``
    next to the output file and referenced with relative paths. Returns an
    empty string when the document has no content.
    """
    assets_dir = assets_dir_for(output)
    counter = [0]
    with source.open('rb') as stream:
        result = mammoth.convert_to_html(
            stream, convert_image=mammoth.images.img_element(_image_handler(assets_dir, counter))
        )
    markdown = html_to_markdown(result.value)
    attachments = _extract_embeddings(source, assets_dir)
    if attachments:
        markdown = _append_attachments(markdown, attachments, assets_dir)
    return markdown.strip('\n')
