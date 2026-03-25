"""Zip-bomb guards for package-based formats (docx, pptx, xlsx).

Office documents are zip packages that often come from untrusted
sources. Before any entry is decompressed into memory, the declared
uncompressed sizes are checked against fixed limits; exceeding them
raises :class:`ZipBombError`, which the CLI reports as a failed
conversion.
"""

import zipfile
from pathlib import Path

MAX_TOTAL_UNCOMPRESSED = 1 << 30
MAX_ENTRY_UNCOMPRESSED = 512 << 20


class ZipBombError(ValueError):
    """Raised when a zip package exceeds safe decompression limits."""


def guard_zip(source: Path) -> None:
    """Reject packages whose declared uncompressed size is too large.

    Files that are not zip packages are ignored here; the format library
    reports them with its own error.
    """
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile:
        return
    with archive:
        total = 0
        for info in archive.infolist():
            if info.file_size > MAX_ENTRY_UNCOMPRESSED:
                raise ZipBombError(f'zip entry too large: {source.name} :: {info.filename} ({info.file_size} bytes)')
            total += info.file_size
        if total > MAX_TOTAL_UNCOMPRESSED:
            raise ZipBombError(f'zip package too large: {source.name} ({total} bytes uncompressed)')
