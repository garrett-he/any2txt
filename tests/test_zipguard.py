"""Tests for any2txt.zipguard."""

import zipfile
from pathlib import Path

import pytest

from any2txt import zipguard
from any2txt.zipguard import ZipBombError, guard_zip


def write_zip(path: Path, entries: dict[str, bytes]) -> Path:
    """Create a zip archive with the given entries."""
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_guard_zip_accepts_normal_package(tmp_path: Path) -> None:
    """A small package passes the guard."""
    guard_zip(write_zip(tmp_path / 'ok.docx', {'word/document.xml': b'<document/>'}))


def test_guard_zip_ignores_non_zip_files(tmp_path: Path) -> None:
    """Files that are not zip packages are left to the format library."""
    source = tmp_path / 'not.docx'
    source.write_bytes(b'not a zip')
    guard_zip(source)


def test_guard_zip_rejects_large_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A single entry above the per-entry cap is rejected before decompression."""
    monkeypatch.setattr(zipguard, 'MAX_ENTRY_UNCOMPRESSED', 4)
    source = write_zip(tmp_path / 'bomb.docx', {'word/media/image1.png': b'12345'})
    with pytest.raises(ZipBombError, match='zip entry too large'):
        guard_zip(source)


def test_guard_zip_rejects_large_total(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The combined uncompressed size is capped as well."""
    monkeypatch.setattr(zipguard, 'MAX_TOTAL_UNCOMPRESSED', 5)
    source = write_zip(tmp_path / 'bomb.docx', {'a.xml': b'1234', 'b.xml': b'5678'})
    with pytest.raises(ZipBombError, match='zip package too large'):
        guard_zip(source)
