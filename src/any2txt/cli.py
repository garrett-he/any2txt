"""CLI for any2txt."""

import typer

app = typer.Typer()


@app.command()
def main() -> None:
    """Print a greeting."""
    typer.echo('Hello, world!')
