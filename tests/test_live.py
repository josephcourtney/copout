"""Checks against the user's real Atuin shell integration."""

import errno
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

_PROMPT = b"__COPOUT_TEST_PROMPT__ "
_TIMEOUT = 15.0


def _require_live_shell() -> str:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("requires zsh")
    if shutil.which("atuin") is None:
        pytest.skip("requires atuin")
    return zsh


def _read_until(fd: int, marker: bytes, *, timeout: float = _TIMEOUT) -> bytes:
    deadline = time.monotonic() + timeout
    output = bytearray()
    while marker not in output:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            pytest.fail(f"timed out waiting for {marker!r}; terminal output: {bytes(output)!r}")
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            continue
        try:
            chunk = os.read(fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        output.extend(chunk)
    if marker not in output:
        pytest.fail(f"shell exited before {marker!r}; terminal output: {bytes(output)!r}")
    return bytes(output)


def _send(fd: int, command: str) -> None:
    os.write(fd, command.encode() + b"\n")


def _run_probe_in_atuin_shell(output_path: Path) -> None:
    zsh = _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(zsh, [zsh, "-il"])

    try:
        # Input is buffered by the PTY until zsh is ready. Construct the prompt
        # from separate fragments so terminal echo of this command cannot itself
        # contain the sentinel that marks a completed command lifecycle.
        _send(
            fd,
            "PROMPT='__COPOUT_TEST_'$'PROMPT__ ' RPROMPT='' PROMPT_EOL_MARK=''",
        )
        _read_until(fd, _PROMPT)

        _send(fd, "printf 'copout-live-probe\\n'")
        _read_until(fd, _PROMPT)

        # Run Copout only after the next prompt: Atuin has then finalized the probe
        # record and its captured terminal output. Redirect JSON to avoid parsing
        # terminal echo/prompt control sequences from the PTY itself.
        quoted_launcher = str(launcher).replace("'", "'\\''")
        quoted_output = str(output_path).replace("'", "'\\''")
        _send(
            fd,
            f"'{quoted_launcher}' --print --json --last 10 > '{quoted_output}'",
        )
        _read_until(fd, _PROMPT)
        _send(fd, "exit")
    finally:
        os.close(fd)
        _, status = os.waitpid(pid, 0)
        if status != 0:
            pytest.fail(f"interactive zsh exited with wait status {status}")


def test_live_shell_capture(tmp_path: Path) -> None:
    output_path = tmp_path / "copout-live.json"
    _run_probe_in_atuin_shell(output_path)

    runs = json.loads(output_path.read_text())["runs"]
    probes = [run for run in runs if run["command"].strip() == "printf 'copout-live-probe\\n'"]
    assert probes, "the child Atuin-integrated shell did not record the standalone probe"
    output = probes[-1]["output"]
    assert output["state"] == "captured", (
        output.get("error") or "the real Atuin output cache did not capture the probe"
    )

    # Atuin may retain terminal-cell padding and final blank rows in its capture. Copout removes
    # whitespace only from the end of the complete captured output.
    assert output["text"] == "copout-live-probe"


def test_live_clipboard_delivery_does_not_fork_after_grpc(tmp_path: Path) -> None:
    _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    clipboard_helper = tmp_path / "pbcopy"
    clipboard_helper.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read()\n")
    clipboard_helper.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join((str(tmp_path), env.get("PATH", "")))
    result = subprocess.run(
        [str(launcher)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
