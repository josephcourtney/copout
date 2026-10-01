set shell := ["bash", "-euo", "pipefail", "-c"]

PYTHON := ".venv/bin/python"
RUFF := ".venv/bin/ruff"
TY := ".venv/bin/ty"
PYTEST := ".venv/bin/pytest"
UV := "uv"

help:
  @printf '%s\n' \
    'Copout development commands:' \
    '  just setup                 Install/sync development dependencies' \
    '  just fix                   Apply Ruff formatting and automatic lint fixes' \
    '  just repair                Sync, fix, then run the full validation suite' \
    '  just lint                  Ruff check with automatic fixes' \
    '  just lint --unsafe-fixes   Also apply Ruff unsafe fixes' \
    '  just format                Apply Ruff formatting' \
    '  just typecheck             ty type checking' \
    '  just test                  pytest' \
    '  just check                 Run non-mutating lint, format, typecheck, and tests' \
    '  just build                 Build wheel and sdist'

setup:
  {{UV}} sync

fix:
  just format
  just lint

repair:
  just setup
  just fix
  just check

[arg("unsafe-fixes", long, value="true")]
lint unsafe-fixes="false":
  #!/usr/bin/env bash
  set -euo pipefail
  args=("{{RUFF}}" check --fix)
  if [ "{{unsafe-fixes}}" = "true" ]; then
    args+=(--unsafe-fixes)
  fi
  args+=(src tests)
  "${args[@]}"

format:
  {{RUFF}} format src tests

typecheck:
  {{TY}} check src tests

test:
  {{PYTEST}} -q

check:
  {{RUFF}} check src tests
  {{RUFF}} format --check src tests
  just typecheck
  just test

build:
  {{UV}} build

clean:
  rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build
  find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
