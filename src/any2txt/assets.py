"""Asset sinks and the asset-directory convention.

Converters never touch the filesystem: they hand every extracted image or
embedded object to an :class:`AssetSink` and use the URL it returns in
the Markdown. Returning ``None`` means the asset cannot be represented in
the active mode, so the converter drops the reference instead of writing
a dangling link.
"""

import base64
import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Protocol

# Data URIs are only rendered for raster/vector image types that
# renderers accept; anything else is dropped in embed mode.
WEB_IMAGE_MIME = frozenset({'image/png', 'image/gif', 'image/jpeg', 'image/webp', 'image/svg+xml'})

MAX_EMBED_IMAGE_BYTES = 2 * 1024 * 1024
MAX_EMBED_TOTAL_BYTES = 16 * 1024 * 1024


class AssetMode(StrEnum):
    """How extracted resources accompany the Markdown output."""

    DIR = 'dir'
    DROP = 'drop'
    EMBED = 'embed'


class AssetSink(Protocol):
    """Collects resources of one conversion and returns their Markdown URLs."""

    def put(self, name: str, data: bytes, mime: str) -> str | None:
        """Return the URL to reference an asset by, or None to drop it."""
        ...


def assets_dir_for(output: Path) -> Path:
    """Return the asset directory that accompanies one output file."""
    return output.parent / f'{output.stem}_files'


class DirSink:
    """Write assets into one directory and reference them relatively."""

    def __init__(self, directory: Path) -> None:
        """Create a sink that writes into directory."""
        self._directory = directory

    def put(self, name: str, data: bytes, mime: str) -> str | None:
        """Write one asset and return its path relative to the Markdown file."""
        self._directory.mkdir(parents=True, exist_ok=True)
        (self._directory / name).write_bytes(data)
        return f'{self._directory.name}/{name}'


class DropSink:
    """Discard every asset, so the Markdown stays free of links."""

    def put(self, name: str, data: bytes, mime: str) -> None:
        """Drop the asset."""
        return None


class DataUriSink:
    """Inline assets as ``data:`` URIs so the Markdown is self-contained.

    Only renderable image types are embedded; oversized images and
    non-image resources are dropped. Identical payloads are embedded once
    and shared.
    """

    def __init__(self) -> None:
        """Create an empty sink with no embedded bytes yet."""
        self._seen: dict[str, str] = {}
        self._total = 0

    def put(self, name: str, data: bytes, mime: str) -> str | None:
        """Return a data URI for one image, or None when it cannot be embedded."""
        base_mime = mime.split(';')[0].strip().lower()
        if base_mime not in WEB_IMAGE_MIME or len(data) > MAX_EMBED_IMAGE_BYTES:
            return None
        digest = hashlib.sha256(data).hexdigest()
        cached = self._seen.get(digest)
        if cached is not None:
            return cached
        if self._total + len(data) > MAX_EMBED_TOTAL_BYTES:
            return None
        payload = base64.b64encode(data).decode('ascii')
        url = f'data:{base_mime};base64,{payload}'
        self._seen[digest] = url
        self._total += len(data)
        return url


def make_sink(mode: AssetMode, output: Path | None) -> AssetSink:
    """Return the sink for one conversion.

    ``dir`` requires an output path because assets land next to it;
    ``drop`` and ``embed`` never touch the filesystem.
    """
    if mode is AssetMode.DROP:
        return DropSink()
    if mode is AssetMode.EMBED:
        return DataUriSink()
    if output is None:
        raise ValueError('asset mode "dir" requires an output path')
    return DirSink(assets_dir_for(output))
