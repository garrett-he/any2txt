"""Tests for any2txt.pdf conversion.

Fixtures are built with PyMuPDF itself, so no real PDF files, network,
or external tools are required.
"""

import base64
from pathlib import Path

import pymupdf as fitz

from any2txt.pdf import convert_pdf

PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)


def build_pdf(path: Path) -> Path:
    """Create a one-page PDF with a title, a body, an image, and a link."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 40, 550, 100), 'Big Title', fontname='helv', fontsize=24)
    page.insert_textbox(fitz.Rect(50, 110, 550, 170), 'Body line one.\nBody line two.', fontname='helv', fontsize=11)
    page.insert_textbox(fitz.Rect(50, 180, 300, 205), 'see link text', fontname='helv', fontsize=11)
    page.insert_link({'kind': fitz.LINK_URI, 'from': fitz.Rect(50, 180, 110, 200), 'uri': 'https://example.com'})
    page.insert_image(fitz.Rect(50, 220, 150, 260), stream=PNG_1X1)
    doc.save(str(path))
    doc.close()
    return path


def convert_fixture(tmp_path: Path) -> str:
    """Build a pdf fixture, convert it, and return the Markdown."""
    source = build_pdf(tmp_path / 'doc.pdf')
    return convert_pdf(source, tmp_path / 'doc.md')


def test_convert_font_size_headings(tmp_path: Path) -> None:
    """Text much larger than the body becomes an ATX heading."""
    markdown = convert_fixture(tmp_path)
    assert '# Big Title' in markdown
    assert 'Body line one.' in markdown
    assert 'Body line two.' in markdown


def test_convert_image_extracts_to_assets(tmp_path: Path) -> None:
    """Pictures are written into the assets directory and referenced."""
    markdown = convert_fixture(tmp_path)
    assets = tmp_path / 'doc_files'
    pictures = list(assets.glob('page1_image*.png'))
    assert len(pictures) == 1
    assert pictures[0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert 'doc_files/page1_image1.png' in markdown


def test_convert_uri_links(tmp_path: Path) -> None:
    """URI link annotations become Markdown links."""
    markdown = convert_fixture(tmp_path)
    assert '[see link text](https://example.com)' in markdown


def test_convert_empty_pdf(tmp_path: Path) -> None:
    """A pdf without content converts to an empty string."""
    source = tmp_path / 'empty.pdf'
    doc = fitz.open()
    doc.new_page()
    doc.save(str(source))
    doc.close()
    assert convert_pdf(source, tmp_path / 'empty.md') == ''
