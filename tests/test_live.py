"""Opt-in check of output captured by the user's real Atuin shell integration."""

import json
import os
import subprocess
import sysconfig
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.environ.get("COPOUT_LIVE_ATUIN") != "1",
    reason="requires an Atuin-integrated shell with the documented probe command recorded",
)
def test_live_shell_capture() -> None:
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    result = subprocess.run(
        [str(launcher), "--print", "--json", "--last", "10"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    runs = json.loads(result.stdout)["runs"]
    probes = [run for run in runs if run["command"].strip() == "printf 'copout-live-probe\\n'"]
    assert probes, (
        "No completed standalone probe in the last 10 commands of this Atuin session. "
        "Enter printf 'copout-live-probe\\n' alone, wait for the next prompt, then run this test. "
        "Do not paste the probe and pytest together; repeat the probe after opening a new terminal."
    )
    output = probes[-1]["output"]
    assert output["state"] == "captured", (
        output.get("error") or "The real Atuin output cache did not capture the probe"
    )

    # Atuin captures rendered terminal contents rather than raw stdout. Its VT100 renderer may
    # discard the final newline and retain blank terminal cells as trailing spaces, so verify the
    # visible probe text without rewriting the value Copout actually returns.
    assert output["text"].replace("\r\n", "\n").rstrip(" \n") == "copout-live-probe"
