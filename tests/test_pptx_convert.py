"""Tests for any2txt.pptx conversion.

Fixtures are built with python-pptx itself (its bundled default
template), so no real PowerPoint files, network, or external tools are
required.
"""

import base64
import io
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Inches

from any2txt.assets import DataUriSink, DirSink
from any2txt.pptx import convert_pptx

if TYPE_CHECKING:
    from pptx.shapes.autoshape import Shape
    from pptx.text.text import TextFrame

PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)


def build_deck(path: Path) -> Path:
    """Create a two-slide deck with bullets, a table, a picture, and notes."""
    presentation = Presentation()

    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    cast('Shape', slide.shapes.title).text = 'My Deck'
    body = cast('Shape', slide.placeholders[1]).text_frame
    body.text = 'first'
    second = body.add_paragraph()
    second.text = 'second'
    second.level = 1

    slide2 = presentation.slides.add_slide(presentation.slide_layouts[5])
    frame = slide2.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(1.5))
    frame.table.cell(0, 0).text = 'A1'
    frame.table.cell(0, 1).text = 'B1'
    frame.table.cell(1, 0).text = 'A2'
    frame.table.cell(1, 1).text = 'B2'
    slide2.shapes.add_picture(io.BytesIO(PNG_1X1), Inches(1), Inches(3))
    cast('TextFrame', slide2.notes_slide.notes_text_frame).text = 'remember this'

    presentation.save(str(path))
    return path


def convert_fixture(tmp_path: Path) -> str:
    """Build a deck fixture, convert it, and return the Markdown."""
    source = build_deck(tmp_path / 'deck.pptx')
    return convert_pptx(source, DirSink(tmp_path / 'deck_files'))


def test_convert_titles_and_bullets(tmp_path: Path) -> None:
    """Slide titles become headings; body placeholders become bullet lists."""
    markdown = convert_fixture(tmp_path)
    assert '## My Deck' in markdown
    assert '- first' in markdown
    assert '  - second' in markdown


def test_convert_table(tmp_path: Path) -> None:
    """Tables become Markdown pipe tables."""
    markdown = convert_fixture(tmp_path)
    assert '| A1 | B1 |' in markdown
    assert '| --- | --- |' in markdown
    assert '| A2 | B2 |' in markdown


def test_convert_picture_extracts_to_assets(tmp_path: Path) -> None:
    """Pictures are written into the assets directory and referenced."""
    markdown = convert_fixture(tmp_path)
    assets = tmp_path / 'deck_files'
    pictures = list(assets.glob('slide2_image*.png'))
    assert len(pictures) == 1
    assert pictures[0].read_bytes() == PNG_1X1
    assert 'deck_files/slide2_image1.png' in markdown


def test_convert_skips_linked_only_picture(tmp_path: Path) -> None:
    """A picture linked to an external file (no embedded bits) is skipped."""
    source = build_deck(tmp_path / 'deck.pptx')
    presentation = Presentation(str(source))
    picture = next(shape for shape in presentation.slides[1].shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE)
    blip_fill = picture._element.find(qn('p:blipFill'))
    assert blip_fill is not None
    blip = blip_fill.find(qn('a:blip'))
    assert blip is not None
    del blip.attrib[qn('r:embed')]
    linked = tmp_path / 'linked.pptx'
    presentation.save(str(linked))
    markdown = convert_pptx(linked, DirSink(tmp_path / 'linked_files'))
    assert '## Slide 2' in markdown
    assert 'slide2_image' not in markdown


def test_convert_skips_unrecognized_image_part(tmp_path: Path) -> None:
    """A picture whose rel points to a non-image part is skipped."""
    source = build_deck(tmp_path / 'deck.pptx')
    presentation = Presentation(str(source))
    picture = next(shape for shape in presentation.slides[1].shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE)
    blip_fill = picture._element.find(qn('p:blipFill'))
    assert blip_fill is not None
    blip = blip_fill.find(qn('a:blip'))
    assert blip is not None
    blip.set(qn('r:embed'), 'rId1')
    repointed = tmp_path / 'repointed.pptx'
    presentation.save(str(repointed))
    markdown = convert_pptx(repointed, DirSink(tmp_path / 'repointed_files'))
    assert '## Slide 2' in markdown
    assert 'slide2_image' not in markdown


def test_convert_notes_as_blockquote(tmp_path: Path) -> None:
    """Speaker notes are kept as blockquotes."""
    markdown = convert_fixture(tmp_path)
    assert '> remember this' in markdown


def test_convert_empty_presentation(tmp_path: Path) -> None:
    """A presentation without slides converts to an empty string."""
    source = tmp_path / 'empty.pptx'
    Presentation().save(str(source))
    assert convert_pptx(source, DirSink(tmp_path / 'empty_files')) == ''


def test_convert_picture_embeds_data_uri(tmp_path: Path) -> None:
    """Embed mode inlines pictures and writes nothing to disk."""
    markdown = convert_pptx(build_deck(tmp_path / 'deck.pptx'), DataUriSink())
    assert '![slide2_image1.png](data:image/png;base64,' in markdown
    assert not (tmp_path / 'deck_files').exists()
