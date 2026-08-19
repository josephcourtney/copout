set shell := ["bash", "-euo", "pipefail", "-c"]

PYTHON := ".venv/bin/python"
RUFF := ".venv/bin/ruff"
TY := ".venv/bin/ty"
PYTEST := ".venv/bin/pytest"
UV := "uv"

help:
  @printf '%s\n' \
    'Copout development commands:' \
    '  just setup      Install/sync development dependencies' \
    '  just lint       Ruff check' \
    '  just format     Ruff formatting check' \
    '  just typecheck  ty type checking' \
    '  just test       pytest' \
    '  just check      Run lint, format, typecheck, and tests' \
    '  just build      Build wheel and sdist'

setup:
  {{UV}} sync

lint:
  {{RUFF}} check src tests

format:
  {{RUFF}} format --check src tests

typecheck:
  {{TY}} check src tests

test:
  {{PYTEST}} -q

check:
  just lint
  just format
  just typecheck
  just test

build:
  {{UV}} build

clean:
  rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build
  find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
