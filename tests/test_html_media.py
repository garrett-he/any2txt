"""Tests for any2txt.media.html."""

from pathlib import Path

from any2txt.assets import assets_dir_for
from any2txt.media.html import copy_local_images, is_html


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


def test_copy_local_images_copies_and_rewrites(tmp_path: Path) -> None:
    """A local relative image is copied into the assets dir and its src rewritten."""
    source = tmp_path / 'page.html'
    (tmp_path / 'img').mkdir()
    (tmp_path / 'img' / 'photo one.png').write_bytes(b'png')
    source.write_text('<img src="img/photo%20one.png">', encoding='utf-8')
    output = tmp_path / 'out' / 'page.md'

    result = copy_local_images(source.read_text(encoding='utf-8'), source, assets_dir_for(output))

    assets_dir = assets_dir_for(output)
    assert (assets_dir / 'photo_one.png').read_bytes() == b'png'
    assert '<img src="page_files/photo_one.png"/>' in result


def test_copy_local_images_keeps_remote_and_data_sources(tmp_path: Path) -> None:
    """Remote URLs and data URIs are left untouched and nothing is copied."""
    source = tmp_path / 'page.html'
    html = '<img src="https://example.com/a.png"><img src="data:image/png;base64,AAAA">'
    source.write_text(html, encoding='utf-8')
    assets_dir = tmp_path / 'page_files'

    result = copy_local_images(html, source, assets_dir)

    assert not assets_dir.exists()
    assert 'src="https://example.com/a.png"' in result
    assert 'src="data:image/png;base64,AAAA"' in result


def test_copy_local_images_leaves_missing_files(tmp_path: Path) -> None:
    """References to nonexistent local files are left unchanged."""
    source = tmp_path / 'page.html'
    html = '<img src="missing.png">'
    source.write_text(html, encoding='utf-8')

    result = copy_local_images(html, source, tmp_path / 'page_files')

    assert 'src="missing.png"' in result


def test_copy_local_images_handles_basename_conflicts(tmp_path: Path) -> None:
    """Two local images sharing a basename get distinct asset names."""
    source = tmp_path / 'page.html'
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    (tmp_path / 'a' / 'pic.png').write_bytes(b'first')
    (tmp_path / 'b' / 'pic.png').write_bytes(b'second')
    html = '<img src="a/pic.png"><img src="b/pic.png">'
    source.write_text(html, encoding='utf-8')
    assets_dir = tmp_path / 'page_files'

    result = copy_local_images(html, source, assets_dir)

    assert (assets_dir / 'pic.png').read_bytes() == b'first'
    assert (assets_dir / 'pic_1.png').read_bytes() == b'second'
    assert 'src="page_files/pic.png"' in result
    assert 'src="page_files/pic_1.png"' in result


def test_copy_local_images_resolves_windows_separators(tmp_path: Path) -> None:
    """Windows-style relative paths are resolved on any platform."""
    source = tmp_path / 'page.html'
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'Evernote').write_bytes(b'jpeg')
    html = '<img src="dir\\Evernote">'
    source.write_text(html, encoding='utf-8')
    assets_dir = tmp_path / 'page_files'

    result = copy_local_images(html, source, assets_dir)

    assert (assets_dir / 'Evernote').read_bytes() == b'jpeg'
    assert 'src="page_files/Evernote"' in result
