"""Tests for any2txt CLI."""

from typer.testing import CliRunner

from any2txt.cli import app

runner = CliRunner()


def test_cli_prints_hello_world() -> None:
    """The CLI prints 'Hello, world!' by default."""
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert 'Hello, world!' in result.output
