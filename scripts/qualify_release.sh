#!/usr/bin/env bash
# Local, non-publishing release qualification; must run on the target macOS host.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

for executable in uv just zsh atuin; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    printf 'Release qualification requires %s on PATH\n' "$executable" >&2
    exit 2
  fi
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf 'Live Kitty/Atuin release qualification requires macOS\n' >&2
  exit 2
fi

uv sync --locked
just check

# A green pytest result with skipped live tests does not qualify the release.
live_output="$(uv run pytest tests/test_live.py -q -rs 2>&1)" || {
  printf '%s\n' "$live_output"
  exit 1
}
printf '%s\n' "$live_output"
if grep -Eq '[0-9]+ skipped' <<<"$live_output"; then
  printf 'Live-shell tests skipped; release is not qualified\n' >&2
  exit 2
fi


# Verify headless CLI behavior against the current Atuin session.
.venv/bin/python - <<'PY'
import json
import subprocess
from pathlib import Path

copout = str(Path(".venv/bin/copout").resolve())
unbound = subprocess.run(
    [copout, "-p"],
    stdin=subprocess.DEVNULL,
    capture_output=True,
    text=True,
    start_new_session=True,
    check=False,
)
if unbound.returncode == 0:
    raise SystemExit("Bare picker unexpectedly succeeded without a controlling TTY")

selected = subprocess.run(
    [copout, "1", "-p", "--json"],
    stdin=subprocess.DEVNULL,
    capture_output=True,
    text=True,
    start_new_session=True,
    check=False,
)
if selected.returncode != 0:
    raise SystemExit(f"Headless explicit selector failed: {selected.stderr}")
payload = json.loads(selected.stdout)
if not payload.get("runs"):
    raise SystemExit("Headless selector returned no runs")
print("Verified non-TTY rejection and headless explicit selection")
PY

just build

.venv/bin/python - <<'PY'
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

project = tomllib.loads(Path("pyproject.toml").read_text())
version = project["project"]["version"]
dist = Path("dist")
wheels = sorted(dist.glob(f"copout-{version}-*.whl"))
sdist = dist / f"copout-{version}.tar.gz"
if len(wheels) != 1 or not sdist.is_file():
    raise SystemExit(f"Expected one wheel and sdist for {version}: {wheels}, {sdist}")

with zipfile.ZipFile(wheels[0]) as archive:
    members = set(archive.namelist())
    for file in ("copout/cli.py", "copout/terminal.py", "copout/render.py"):
        if file not in members:
            raise SystemExit(f"Missing wheel module: {file}")
    metadata_path = next((item for item in members if item.endswith(".dist-info/METADATA")), None)
    if metadata_path is None:
        raise SystemExit("Wheel has no METADATA")
    metadata = Parser().parsestr(archive.read(metadata_path).decode())
    if metadata.get("Name") != "copout" or metadata.get("Version") != version:
        raise SystemExit("Built wheel version/name mismatch")

with tarfile.open(sdist, "r:gz") as archive:
    members = archive.getnames()
    for path in ("pyproject.toml", "src/copout/terminal.py", "src/copout/cli.py"):
        if not any(member.endswith("/" + path) for member in members):
            raise SystemExit(f"Missing sdist source: {path}")
print(f"Validated wheel {wheels[0].name} and sdist {sdist.name}")
PY

git diff --exit-code -- pyproject.toml uv.lock README.md CHANGELOG.md PLAN.md TODO.md
printf 'Automated macOS release qualification passed; perform documented manual Kitty checks.\n'
