"""Tests for any2txt.docx conversion.

Fixtures are minimal OOXML packages built with zipfile, so no real Word
documents, network, or external tools are required.
"""

import base64
import zipfile
from pathlib import Path

from any2txt.docx import convert_docx

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

NUMBERING = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W_NS}">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#8226;"/>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>'''

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com" TargetMode="External"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# A WPS-style sheet: the second style lacks the required w:type attribute.
STYLES = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:style w:type="paragraph" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:styleId="b4d6bf" w:customStyle="1">
    <w:name w:val="Emphasis"/>
    <w:rPr>
      <w:b/>
    </w:rPr>
  </w:style>
</w:styles>'''

PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)

DOCUMENT_OPEN = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>'''

DOCUMENT_CLOSE = """  </w:body>
</w:document>"""


def build_docx(path: Path, body: str, extras: dict[str, bytes] | None = None) -> Path:
    """Create a minimal docx package with the given body XML."""
    parts = {
        '[Content_Types].xml': CONTENT_TYPES,
        '_rels/.rels': ROOT_RELS,
        'word/_rels/document.xml.rels': DOCUMENT_RELS,
        'word/numbering.xml': NUMBERING,
        'word/styles.xml': STYLES,
        'word/document.xml': f'{DOCUMENT_OPEN}{body}{DOCUMENT_CLOSE}',
    }
    with zipfile.ZipFile(path, 'w') as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
        for name, data in (extras or {}).items():
            archive.writestr(name, data)
    return path


def convert_fixture(tmp_path: Path, body: str, extras: dict[str, bytes] | None = None) -> str:
    """Build a docx fixture, convert it, and return the Markdown."""
    source = build_docx(tmp_path / 'doc.docx', body, extras)
    return convert_docx(source, tmp_path / 'doc.md')


def test_convert_headings_and_emphasis(tmp_path: Path) -> None:
    """Headings become ATX markers and run properties become emphasis."""
    body = """
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>My Title</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Sub Title</w:t></w:r></w:p>
    <w:p>
      <w:r><w:rPr><w:b/></w:rPr><w:t>bold</w:t></w:r>
      <w:r><w:t> and </w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>italic</w:t></w:r>
    </w:p>"""
    markdown = convert_fixture(tmp_path, body)
    assert '# My Title' in markdown
    assert '## Sub Title' in markdown
    assert '**bold**' in markdown
    assert '*italic*' in markdown


def test_convert_bullet_list(tmp_path: Path) -> None:
    """Numbered paragraphs become Markdown bullet items."""
    body = """
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>first</w:t></w:r></w:p>
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>second</w:t></w:r></w:p>"""
    markdown = convert_fixture(tmp_path, body)
    assert '- first' in markdown
    assert '- second' in markdown


def test_convert_table(tmp_path: Path) -> None:
    """Tables become Markdown pipe tables."""
    body = """
    <w:tbl>
      <w:tr><w:tc><w:p><w:r><w:t>A1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B1</w:t></w:r></w:p></w:tc></w:tr>
      <w:tr><w:tc><w:p><w:r><w:t>A2</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B2</w:t></w:r></w:p></w:tc></w:tr>
    </w:tbl>"""
    markdown = convert_fixture(tmp_path, body)
    assert '| A1 | B1 |' in markdown
    assert '| --- | --- |' in markdown
    assert '| A2 | B2 |' in markdown


def test_convert_hyperlink(tmp_path: Path) -> None:
    """Hyperlinks become Markdown links."""
    body = """
    <w:p><w:hyperlink r:id="rId2"><w:r><w:t>link text</w:t></w:r></w:hyperlink></w:p>"""
    markdown = convert_fixture(tmp_path, body)
    assert '[link text](https://example.com)' in markdown


def test_convert_image_extracts_to_assets(tmp_path: Path) -> None:
    """Inline images are written into the assets directory and referenced."""
    body = """
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline>
            <wp:extent cx="914400" cy="914400"/>
            <a:graphic>
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic>
                  <pic:nvPicPr><pic:cNvPr id="1" name="img"/><pic:cNvPicPr/></pic:nvPicPr>
                  <pic:blipFill><a:blip r:embed="rId3"/></pic:blipFill>
                  <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>"""
    markdown = convert_fixture(tmp_path, body, {'word/media/image1.png': PNG_1X1})
    assets = tmp_path / 'doc_files'
    assert (assets / 'image1.png').is_file()
    assert (assets / 'image1.png').read_bytes() == PNG_1X1
    assert 'doc_files/image1.png' in markdown


def test_convert_embeddings_appends_attachments(tmp_path: Path) -> None:
    """OLE embedded objects are extracted and listed in an appendix."""
    markdown = convert_fixture(
        tmp_path,
        '<w:p><w:r><w:t>hello</w:t></w:r></w:p>',
        {'word/embeddings/oleObject1.bin': b'embedded data'},
    )
    assets = tmp_path / 'doc_files'
    assert (assets / 'oleObject1.bin').read_bytes() == b'embedded data'
    assert '## 附件' in markdown
    assert '[oleObject1.bin](doc_files/oleObject1.bin)' in markdown


def test_convert_empty_document(tmp_path: Path) -> None:
    """An empty document converts to an empty string."""
    assert convert_fixture(tmp_path, '') == ''


def test_convert_tolerates_styles_without_type(tmp_path: Path) -> None:
    """WPS-style sheets missing w:type do not crash the conversion."""
    body = """
    <w:p>
      <w:pPr><w:pStyle w:val="b4d6bf"/></w:pPr>
      <w:r><w:t>styled text</w:t></w:r>
    </w:p>"""
    markdown = convert_fixture(tmp_path, body)
    assert 'styled text' in markdown
