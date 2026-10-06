"""Checks against the user's real Atuin shell integration."""

import errno
import json
import os
import pty
import select
import shlex
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_TIMEOUT = 20.0
_READY = b"__COPOUT_READY__"
_PROBE_DONE = b"__COPOUT_PROBE_DONE__"
_QUERY_DONE = b"__COPOUT_QUERY_DONE__"


@dataclass(frozen=True, slots=True)
class _Probe:
    name: str
    command: str
    markers: tuple[str, ...]
    expected_status: int = 0


@dataclass(frozen=True, slots=True)
class _ProbeSession:
    runs: list[dict[str, Any]]
    terminal_output: dict[str, bytes]


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


def _split_literal(marker: str) -> str:
    """Return adjacent shell literals whose source never contains the full marker."""
    assert "'" not in marker
    midpoint = max(1, len(marker) // 2)
    return f"'{marker[:midpoint]}''{marker[midpoint:]}'"


def _printf_probe(marker: str, *, stderr: bool = False, newline: bool = True) -> str:
    format_string = "%s\\n" if newline else "%s"
    redirect = " >&2" if stderr else ""
    return f"printf '{format_string}' {_split_literal(marker)}{redirect}"


def _child_stderr_probe(marker: str, *, stdout_to_devnull: bool = False) -> str:
    script = f"printf '%s\\n' {_split_literal(marker)} >&2"
    command = f"/bin/sh -c {shlex.quote(script)}"
    if stdout_to_devnull:
        command += " > /dev/null"
    return command


def _python_fd2_probe(marker: str) -> str:
    midpoint = max(1, len(marker) // 2)
    left = marker[:midpoint]
    right = marker[midpoint:]
    program = f'import os; os.write(2, b"{left}" b"{right}\\n")'
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(program)}"


_STDERR_BUILTIN = "__COPOUT_STDERR_BUILTIN__"
_STDERR_NO_NEWLINE = "__COPOUT_STDERR_NO_NEWLINE__"
_STDERR_CHILD = "__COPOUT_STDERR_CHILD__"
_STDERR_REDIRECTED_STDOUT = "__COPOUT_STDERR_STDOUT_REDIRECTED__"
_STDERR_PIPELINE = "__COPOUT_STDERR_PIPELINE__"
_STDERR_FD2 = "__COPOUT_STDERR_FD2__"
_STDOUT_BEFORE = "__COPOUT_STDOUT_BEFORE__"
_STDERR_MIDDLE = "__COPOUT_STDERR_MIDDLE__"
_STDOUT_AFTER = "__COPOUT_STDOUT_AFTER__"
_STDERR_FAILURE = "__COPOUT_STDERR_FAILURE__"

_BASE_STDERR_PROBES = (
    _Probe(
        "builtin-stderr",
        _printf_probe(_STDERR_BUILTIN, stderr=True),
        (_STDERR_BUILTIN,),
    ),
    _Probe(
        "stderr-without-newline",
        _printf_probe(_STDERR_NO_NEWLINE, stderr=True, newline=False),
        (_STDERR_NO_NEWLINE,),
    ),
    _Probe(
        "child-stderr",
        _child_stderr_probe(_STDERR_CHILD),
        (_STDERR_CHILD,),
    ),
    _Probe(
        "stderr-while-stdout-redirected",
        _child_stderr_probe(_STDERR_REDIRECTED_STDOUT, stdout_to_devnull=True),
        (_STDERR_REDIRECTED_STDOUT,),
    ),
    _Probe(
        "stderr-from-pipeline-member",
        f"{_child_stderr_probe(_STDERR_PIPELINE)} | cat",
        (_STDERR_PIPELINE,),
    ),
    _Probe(
        "direct-fd2-write",
        _python_fd2_probe(_STDERR_FD2),
        (_STDERR_FD2,),
    ),
    _Probe(
        "mixed-stdout-stderr",
        "; ".join(
            (
                _printf_probe(_STDOUT_BEFORE),
                _printf_probe(_STDERR_MIDDLE, stderr=True),
                _printf_probe(_STDOUT_AFTER),
            )
        ),
        (_STDOUT_BEFORE, _STDERR_MIDDLE, _STDOUT_AFTER),
    ),
    _Probe(
        "nonzero-stderr",
        f"({_printf_probe(_STDERR_FAILURE, stderr=True)}; exit 17)",
        (_STDERR_FAILURE,),
        expected_status=17,
    ),
)

_RAPID_STDERR_PROBES = tuple(
    _Probe(
        f"rapid-stderr-{index:02d}",
        _printf_probe(marker, stderr=True),
        (marker,),
    )
    for index in range(16)
    for marker in (f"__COPOUT_STDERR_RAPID_{index:02d}__",)
)

_STDERR_PROBES = _BASE_STDERR_PROBES + _RAPID_STDERR_PROBES
_PROBE_BY_NAME = {probe.name: probe for probe in _STDERR_PROBES}


def _run_probes_in_atuin_shell(output_path: Path, probes: tuple[_Probe, ...]) -> _ProbeSession:
    zsh = _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    pid, fd = pty.fork()
    if pid == 0:
        # pytest may itself be running under Atuin's pty-proxy. The PTY created
        # above is a new terminal boundary, so inherited proxy markers would
        # incorrectly tell the child shell that this new PTY is already proxied.
        # Let the child's normal shell startup launch its own proxy instead.
        os.environ.pop("ATUIN_PTY_PROXY_ACTIVE", None)
        os.environ.pop("ATUIN_PTY_PROXY_SOCKET", None)
        os.execv(zsh, [zsh, "-il"])

    quoted_launcher = str(launcher).replace("'", "'\\''")
    quoted_output = str(output_path).replace("'", "'\\''")
    terminal_output: dict[str, bytes] = {}

    try:
        # First establish that startup has completed and zsh is accepting commands.
        _send(fd, _marker_command("__COPOUT_", "READY__"))
        _read_until(fd, _READY)

        for probe in probes:
            for marker in probe.markers:
                assert marker not in probe.command, (
                    f"probe {probe.name!r} contains its complete marker in command input"
                )
            _send(fd, probe.command)
            # The last expected marker is absent from input echo by construction.
            # Seeing it proves the real child PTY received the command's output.
            terminal_output[probe.name] = _read_until(fd, probe.markers[-1].encode())

        # A separate command is a lifecycle barrier. It cannot execute until zsh
        # has completed the final probe and Atuin's post-command hook has run.
        _send(fd, _marker_command("__COPOUT_PROBE_", "DONE__"))
        _read_until(fd, _PROBE_DONE)

        # Include ample room for readiness/barrier commands and any shell-startup
        # history while remaining within the current child Atuin session.
        query_count = max(50, len(probes) * 3)
        _send(
            fd,
            f"'{quoted_launcher}' --print --json --last {query_count} > '{quoted_output}'; "
            + _marker_command("__COPOUT_QUERY_", "DONE__"),
        )
        _read_until(fd, _QUERY_DONE)

        _send(fd, "exit")
        status = _wait_for_child(pid, fd)
    finally:
        os.close(fd)

    if status != 0:
        pytest.fail(f"interactive zsh exited with wait status {status}")

    payload = json.loads(output_path.read_text())
    return _ProbeSession(runs=payload["runs"], terminal_output=terminal_output)


def _find_probe_run(session: _ProbeSession, probe: _Probe) -> dict[str, Any]:
    matches = [run for run in session.runs if run["command"].strip() == probe.command]
    assert matches, f"Atuin history did not contain probe {probe.name!r}: {probe.command!r}"
    return matches[-1]


def _assert_probe_captured(session: _ProbeSession, probe: _Probe) -> str:
    terminal = session.terminal_output[probe.name]
    for marker in probe.markers:
        assert marker.encode() in terminal, (
            f"{probe.name}: {marker!r} was not observed on the child PTY; "
            "the probe itself did not demonstrate terminal emission"
        )

    run = _find_probe_run(session, probe)
    assert run["result"]["status"] == probe.expected_status, (
        f"{probe.name}: unexpected Atuin exit status {run['result']['status']!r}"
    )

    output = run["output"]
    assert output["state"] == "captured", (
        f"{probe.name}: marker reached the child PTY but Atuin output was unavailable: "
        f"{output.get('error') or 'no retrieval error reported'}"
    )
    text = output["text"]
    for marker in probe.markers:
        assert marker in text, (
            f"{probe.name}: {marker!r} reached the real child PTY but is absent from "
            f"Copout's Atuin-retrieved output: {text!r}"
        )
    return text


def test_live_shell_capture(tmp_path: Path) -> None:
    marker = "copout-live-probe"
    probe = _Probe("stdout", _printf_probe(marker), (marker,))
    session = _run_probes_in_atuin_shell(tmp_path / "copout-live.json", (probe,))

    output = _assert_probe_captured(session, probe)

    # Atuin records terminal output, so shell/theme prompt residue may follow the
    # command's output. The probe itself must still be the first captured line.
    assert output.splitlines()[0] == marker


@pytest.fixture(scope="module")
def live_stderr_session(tmp_path_factory: pytest.TempPathFactory) -> _ProbeSession:
    output_path = tmp_path_factory.mktemp("copout-stderr") / "copout-stderr.json"
    return _run_probes_in_atuin_shell(output_path, _STDERR_PROBES)


@pytest.mark.parametrize(
    "probe_name",
    [
        "builtin-stderr",
        "stderr-without-newline",
        "stderr-while-stdout-redirected",
        "stderr-from-pipeline-member",
    ],
)
def test_live_shell_captures_unredirected_stderr(
    live_stderr_session: _ProbeSession,
    probe_name: str,
) -> None:
    _assert_probe_captured(live_stderr_session, _PROBE_BY_NAME[probe_name])


@pytest.mark.parametrize("probe_name", ["child-stderr", "direct-fd2-write"])
def test_live_shell_captures_child_process_stderr(
    live_stderr_session: _ProbeSession,
    probe_name: str,
) -> None:
    _assert_probe_captured(live_stderr_session, _PROBE_BY_NAME[probe_name])


def test_live_shell_preserves_mixed_stdout_stderr_order(
    live_stderr_session: _ProbeSession,
) -> None:
    text = _assert_probe_captured(live_stderr_session, _PROBE_BY_NAME["mixed-stdout-stderr"])

    positions = [text.index(marker) for marker in (_STDOUT_BEFORE, _STDERR_MIDDLE, _STDOUT_AFTER)]
    assert positions == sorted(positions), (
        "mixed stdout/stderr markers were captured but their terminal order changed"
    )


def test_live_shell_captures_stderr_from_nonzero_command(
    live_stderr_session: _ProbeSession,
) -> None:
    _assert_probe_captured(live_stderr_session, _PROBE_BY_NAME["nonzero-stderr"])


def test_live_shell_rapid_stderr_capture_does_not_drop_commands(
    live_stderr_session: _ProbeSession,
) -> None:
    for probe in _RAPID_STDERR_PROBES:
        _assert_probe_captured(live_stderr_session, probe)


def test_live_clipboard_delivery_does_not_fork_after_grpc(tmp_path: Path) -> None:
    _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    clipboard_helper = tmp_path / "pbcopy"
    clipboard_helper.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read()\n")
    clipboard_helper.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join((str(tmp_path), env.get("PATH", "")))
    result = subprocess.run(
        [str(launcher), "1"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
