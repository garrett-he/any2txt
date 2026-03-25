"""Tests for packaged-runtime paths and local model resolution."""

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from any2txt import runtime
from any2txt.asr import faster_whisper


def _not_packaged() -> bool:
    """Pretend the process runs from source."""
    return False


def _packaged() -> bool:
    """Pretend the process runs from a compiled executable."""
    return True


def _app_at(path: Path) -> Callable[[], Path]:
    """Build an app_dir stub returning path."""

    def app_dir() -> Path:
        return path

    return app_dir


def _models_at(path: Path | None) -> Callable[[], Path | None]:
    """Build a models_dir stub returning path."""

    def models_dir() -> Path | None:
        return path

    return models_dir


def test_is_packaged_is_false_in_source_runs() -> None:
    """The test process runs from source, not from a compiled executable."""
    assert runtime.is_packaged() is False


def test_app_dir_uses_the_script_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The executable directory is derived from argv[0]."""
    script = tmp_path / 'any2txt.exe'
    script.write_bytes(b'')
    monkeypatch.setattr(sys, 'argv', [str(script)])
    assert runtime.app_dir() == tmp_path


def test_models_dir_ignores_source_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Source runs use the Hugging Face cache, so there is no local model directory."""
    monkeypatch.delenv(runtime.MODELS_ENV, raising=False)
    monkeypatch.setattr(runtime, 'is_packaged', _not_packaged)
    assert runtime.models_dir() is None


def test_models_dir_uses_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ANY2TXT_MODELS wins in every mode."""
    monkeypatch.setenv(runtime.MODELS_ENV, str(tmp_path))
    monkeypatch.setattr(runtime, 'is_packaged', _not_packaged)
    assert runtime.models_dir() == tmp_path


def test_models_dir_uses_app_dir_when_packaged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Packaged builds look for models next to the executable."""
    monkeypatch.delenv(runtime.MODELS_ENV, raising=False)
    monkeypatch.setattr(runtime, 'is_packaged', _packaged)
    monkeypatch.setattr(runtime, 'app_dir', _app_at(tmp_path))
    assert runtime.models_dir() == tmp_path / 'models'


def test_resolve_model_returns_name_when_unpackaged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Source runs keep passing the model name to faster-whisper."""
    monkeypatch.setattr(faster_whisper, 'models_dir', _models_at(None))
    assert faster_whisper._resolve_model('base') == 'base'


def test_resolve_model_prefers_local_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An extracted models/base directory is passed through as a path."""
    local = tmp_path / 'base'
    local.mkdir()
    monkeypatch.setattr(faster_whisper, 'models_dir', _models_at(tmp_path))
    assert faster_whisper._resolve_model('base') == str(local)


def test_resolve_model_rejects_missing_local_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Packaged builds fail clearly instead of downloading a missing model."""
    monkeypatch.setattr(faster_whisper, 'models_dir', _models_at(tmp_path))
    with pytest.raises(FileNotFoundError, match='not found'):
        faster_whisper._resolve_model('small')
