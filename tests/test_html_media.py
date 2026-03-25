"""Tests for any2txt.media.html."""

from pathlib import Path

from any2txt.assets import DataUriSink, DirSink, DropSink
from any2txt.media.html import is_html, read_html, rewrite_local_images


def test_is_html_known_extensions() -> None:
    """Common HTML extensions are recognized (case-insensitive)."""
    assert is_html(Path('a.html'))
    assert is_html(Path('a.htm'))
    assert is_html(Path('a.HTML'))
    assert is_html(Path('a.Htm'))


def test_is_html_rejects_other_extensions() -> None:
    """Non-HTML extensions are rejected."""
    assert not is_html(Path('a.txt'))
    assert not is_html(Path('a.md'))
    assert not is_html(Path('a'))
    assert not is_html(Path('a.html.txt'))


def test_read_html_utf8_bom(tmp_path: Path) -> None:
    """A UTF-8 BOM is removed from the decoded text."""
    source = tmp_path / 'page.html'
    source.write_bytes(b'\xef\xbb\xbf<p>caf\xc3\xa9</p>')
    assert read_html(source) == '<p>café</p>'


def test_read_html_declared_charset(tmp_path: Path) -> None:
    """A declared legacy charset is honored before the GB18030 fallback."""
    source = tmp_path / 'page.html'
    body = '<meta charset="windows-1252"><p>café</p>'
    source.write_bytes(body.encode('windows-1252'))
    assert 'café' in read_html(source)


def test_read_html_gb18030_fallback(tmp_path: Path) -> None:
    """Legacy Chinese pages without a declaration still decode."""
    source = tmp_path / 'page.html'
    source.write_bytes(b'<p>\xd6\xd0\xce\xc4</p>')
    assert read_html(source) == '<p>中文</p>'


def test_read_html_lossy_fallback(tmp_path: Path) -> None:
    """Undecodable bytes are replaced instead of raising."""
    source = tmp_path / 'page.html'
    source.write_bytes(b'<p>\xff</p>')
    assert '\ufffd' in read_html(source)


def test_rewrite_local_images_copies_and_rewrites(tmp_path: Path) -> None:
    """A local relative image is copied into the assets dir and its src rewritten."""
    source = tmp_path / 'page.html'
    (tmp_path / 'img').mkdir()
    (tmp_path / 'img' / 'photo one.png').write_bytes(b'png')
    source.write_text('<img src="img/photo%20one.png">', encoding='utf-8')

    result = rewrite_local_images(source.read_text(encoding='utf-8'), source, DirSink(tmp_path / 'page_files'))

    assets_dir = tmp_path / 'page_files'
    assert (assets_dir / 'photo_one.png').read_bytes() == b'png'
    assert '<img src="page_files/photo_one.png"/>' in result


def test_rewrite_local_images_keeps_remote_and_data_sources(tmp_path: Path) -> None:
    """Remote URLs and data URIs are left untouched and nothing is copied."""
    source = tmp_path / 'page.html'
    html = '<img src="https://example.com/a.png"><img src="data:image/png;base64,AAAA">'
    source.write_text(html, encoding='utf-8')
    sink = DirSink(tmp_path / 'page_files')

    result = rewrite_local_images(html, source, sink)

    assert not (tmp_path / 'page_files').exists()
    assert 'src="https://example.com/a.png"' in result
    assert 'src="data:image/png;base64,AAAA"' in result


def test_rewrite_local_images_leaves_missing_files(tmp_path: Path) -> None:
    """References to nonexistent local files are left unchanged."""
    source = tmp_path / 'page.html'
    html = '<img src="missing.png">'
    source.write_text(html, encoding='utf-8')

    result = rewrite_local_images(html, source, DirSink(tmp_path / 'page_files'))

    assert 'src="missing.png"' in result


def test_rewrite_local_images_handles_basename_conflicts(tmp_path: Path) -> None:
    """Two local images sharing a basename get distinct asset names."""
    source = tmp_path / 'page.html'
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    (tmp_path / 'a' / 'pic.png').write_bytes(b'first')
    (tmp_path / 'b' / 'pic.png').write_bytes(b'second')
    html = '<img src="a/pic.png"><img src="b/pic.png">'
    source.write_text(html, encoding='utf-8')
    assets_dir = tmp_path / 'page_files'

    result = rewrite_local_images(html, source, DirSink(assets_dir))

    assert (assets_dir / 'pic.png').read_bytes() == b'first'
    assert (assets_dir / 'pic_1.png').read_bytes() == b'second'
    assert 'src="page_files/pic.png"' in result
    assert 'src="page_files/pic_1.png"' in result


def test_rewrite_local_images_resolves_windows_separators(tmp_path: Path) -> None:
    """Windows-style relative paths are resolved on any platform."""
    source = tmp_path / 'page.html'
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'Evernote').write_bytes(b'jpeg')
    html = '<img src="dir\\Evernote">'
    source.write_text(html, encoding='utf-8')
    assets_dir = tmp_path / 'page_files'

    result = rewrite_local_images(html, source, DirSink(assets_dir))

    assert (assets_dir / 'Evernote').read_bytes() == b'jpeg'
    assert 'src="page_files/Evernote"' in result


def test_rewrite_local_images_drops_removed_assets(tmp_path: Path) -> None:
    """When the sink drops an asset, the img element is removed entirely."""
    source = tmp_path / 'page.html'
    (tmp_path / 'pic.png').write_bytes(b'png')
    html = '<p>before</p><img src="pic.png"><p>after</p>'
    source.write_text(html, encoding='utf-8')

    result = rewrite_local_images(html, source, DropSink())

    assert '<img' not in result
    assert '<p>before</p>' in result
    assert '<p>after</p>' in result


def test_rewrite_local_images_embeds_data_uri(tmp_path: Path) -> None:
    """Embed mode inlines local images without writing files."""
    source = tmp_path / 'page.html'
    (tmp_path / 'pic.png').write_bytes(b'png')
    html = '<img src="pic.png">'
    source.write_text(html, encoding='utf-8')

    result = rewrite_local_images(html, source, DataUriSink())

    assert 'src="data:image/png;base64,cG5n"' in result
    assert not (tmp_path / 'page_files').exists()
