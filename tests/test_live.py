"""Checks against the user's real Atuin shell integration."""

import errno
import json
import os
import pty
import select
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

_TIMEOUT = 20.0
_READY = b"__COPOUT_READY__"
_PROBE_DONE = b"__COPOUT_PROBE_DONE__"
_QUERY_DONE = b"__COPOUT_QUERY_DONE__"


def _require_live_shell() -> str:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("requires zsh")
    if shutil.which("atuin") is None:
        pytest.skip("requires atuin")
    return zsh


def _send(fd: int, command: str) -> None:
    os.write(fd, command.encode() + b"\n")


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


def _wait_for_child(pid: int, fd: int, *, timeout: float = _TIMEOUT) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
        if waited_pid == pid:
            return status

        # Keep draining the PTY while the shell exits. Interactive startup and
        # prompt themes can otherwise fill the PTY buffer and block the child.
        readable, _, _ = select.select([fd], [], [], 0.05)
        if readable:
            try:
                os.read(fd, 4096)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise

    os.kill(pid, signal.SIGTERM)
    os.waitpid(pid, 0)
    pytest.fail(f"interactive zsh did not exit within {timeout:g}s")


def _marker_command(prefix: str, suffix: str) -> str:
    # Keep the complete marker out of terminal input echo. _read_until() must
    # observe command output, not merely the echoed command line.
    return f"printf '%s\\n' '{prefix}''{suffix}'"


def _run_probe_in_atuin_shell(output_path: Path) -> None:
    zsh = _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(zsh, [zsh, "-il"])

    quoted_launcher = str(launcher).replace("'", "'\\''")
    quoted_output = str(output_path).replace("'", "'\\''")

    try:
        # First establish that startup has completed and zsh is accepting commands.
        _send(fd, _marker_command("__COPOUT_", "READY__"))
        _read_until(fd, _READY)

        # The barrier is a separate interactive command. It cannot execute until
        # zsh has completed the probe lifecycle, including Atuin's post-command hook.
        _send(fd, "printf 'copout-live-probe\\n'")
        _send(fd, _marker_command("__COPOUT_PROBE_", "DONE__"))
        _read_until(fd, _PROBE_DONE)

        # Query only after the probe has been finalized. The trailing marker lets
        # us observe query completion while continuously draining PTY output.
        _send(
            fd,
            f"'{quoted_launcher}' --print --json --last 10 > '{quoted_output}'; "
            + _marker_command("__COPOUT_QUERY_", "DONE__"),
        )
        _read_until(fd, _QUERY_DONE)

        _send(fd, "exit")
        status = _wait_for_child(pid, fd)
    finally:
        os.close(fd)

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
