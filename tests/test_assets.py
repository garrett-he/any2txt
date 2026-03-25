"""Tests for any2txt.assets."""

import base64
from pathlib import Path

import pytest

from any2txt import assets
from any2txt.assets import AssetMode, DataUriSink, DirSink, DropSink, assets_dir_for, make_sink

PNG = b'\x89PNG\r\n\x1a\npayload'


def test_assets_dir_for_is_sibling_of_output(tmp_path: Path) -> None:
    """Assets for out/page.md land in out/page_files."""
    assert assets_dir_for(tmp_path / 'out' / 'page.md') == tmp_path / 'out' / 'page_files'


def test_dir_sink_writes_file_and_returns_relative_url(tmp_path: Path) -> None:
    """DirSink writes the payload and references it relative to the Markdown."""
    sink = DirSink(tmp_path / 'page_files')
    url = sink.put('pic.png', PNG, 'image/png')
    assert url == 'page_files/pic.png'
    assert (tmp_path / 'page_files' / 'pic.png').read_bytes() == PNG


def test_drop_sink_returns_none() -> None:
    """DropSink never writes anything."""
    assert DropSink().put('pic.png', PNG, 'image/png') is None


def test_data_uri_sink_encodes_payload() -> None:
    """DataUriSink returns a base64 data URI for a web image type."""
    url = DataUriSink().put('pic.png', PNG, 'image/png')
    assert url == f'data:image/png;base64,{base64.b64encode(PNG).decode("ascii")}'


def test_data_uri_sink_strips_mime_parameters() -> None:
    """MIME parameters do not leak into the data URI header."""
    url = DataUriSink().put('pic.png', PNG, 'image/png; charset=binary')
    assert url is not None
    assert url.startswith('data:image/png;base64,')


def test_data_uri_sink_rejects_non_image_types() -> None:
    """Embedded objects that renderers cannot show are dropped."""
    assert DataUriSink().put('ole.bin', b'data', 'application/octet-stream') is None


def test_data_uri_sink_rejects_oversized_images(monkeypatch: pytest.MonkeyPatch) -> None:
    """An image above the per-image cap is dropped."""
    monkeypatch.setattr(assets, 'MAX_EMBED_IMAGE_BYTES', 4)
    assert DataUriSink().put('big.png', b'12345', 'image/png') is None


def test_data_uri_sink_enforces_total_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Images are embedded until the total budget is exhausted."""
    monkeypatch.setattr(assets, 'MAX_EMBED_TOTAL_BYTES', 15)
    sink = DataUriSink()
    assert sink.put('a.png', b'12345678', 'image/png') is not None
    assert sink.put('b.png', b'abcdefgh', 'image/png') is None


def test_data_uri_sink_dedupes_identical_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identical bytes are embedded once and do not consume budget twice."""
    monkeypatch.setattr(assets, 'MAX_EMBED_TOTAL_BYTES', 16)
    sink = DataUriSink()
    first = sink.put('a.png', b'12345678', 'image/png')
    second = sink.put('b.png', b'12345678', 'image/png')
    assert first is not None
    assert second == first
    assert sink.put('c.png', b'abcdefgh', 'image/png') is not None


def test_make_sink_selects_mode(tmp_path: Path) -> None:
    """make_sink maps each mode to its sink implementation."""
    assert isinstance(make_sink(AssetMode.DROP, None), DropSink)
    assert isinstance(make_sink(AssetMode.EMBED, None), DataUriSink)
    assert isinstance(make_sink(AssetMode.DIR, tmp_path / 'out.md'), DirSink)


def test_make_sink_dir_requires_output() -> None:
    """Dir mode needs an output path to place assets next to."""
    with pytest.raises(ValueError, match='requires an output path'):
        make_sink(AssetMode.DIR, None)
