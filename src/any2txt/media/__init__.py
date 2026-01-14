"""Input media handling, one module per media type.

Adding a new media type means adding a module here with its extension
set and a predicate, then including it in :func:`is_supported` below.
The conversion pipeline in cli.py is media-type agnostic and must stay
that way; new types are only scanned and validated here.
"""

from pathlib import Path

from any2txt.media.audio import is_audio
from any2txt.media.docx import is_docx
from any2txt.media.html import is_html
from any2txt.media.image import is_image
from any2txt.media.pptx import is_pptx
from any2txt.media.video import is_video

__all__ = ['is_supported']


def is_supported(path: Path) -> bool:
    """Return True if any registered media type claims the path's extension.

    New media types (pdf, ...) plug in here.
    """
    return is_video(path) or is_audio(path) or is_image(path) or is_docx(path) or is_html(path) or is_pptx(path)
