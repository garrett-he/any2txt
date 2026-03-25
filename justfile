@_default:
    just --list --unsorted

# Install dependencies and pre-commit hooks
install:
    uv sync --extra dev
    uv run pre-commit install

# Run checkers
check:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run pyrefly check
    uv run pyproject-fmt --check pyproject.toml
    uv run rumdl check .

# Run formatters
format:
    uv run ruff format src tests
    uv run pyproject-fmt pyproject.toml
    uv run rumdl check --fix .

# Run tests
test:
    uv run pytest

# Run continuous integration
ci:
    just check
    just test

# Build the project
build:
    uv build

# Build the release artifacts (exe, dependency archive, model archive)
release:
    uv run python packaging/build_release.py

# Publish the project
publish:
    uv publish
