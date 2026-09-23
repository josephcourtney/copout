from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from ._process import run_process
from .atuin import AtuinError, DaemonInfo, HistoryEntry, daemon_info, recent_entries


@dataclass(frozen=True, slots=True)
class Diagnostic:
    atuin_path: str | None = None
    atuin_version: str | None = None
    session_present: bool = False
    daemon_enabled: bool | None = None
    daemon_autostart: bool | None = None
    pty_proxy_enabled: bool | None = None
    output_enabled: bool | None = None
    pty_proxy_active: bool = False
    daemon: DaemonInfo | None = None
    daemon_error: str | None = None
    latest: HistoryEntry | None = None
    history_error: str | None = None


@dataclass(frozen=True, slots=True)
class Verification:
    ok: bool
    message: str


def _command(args: list[str]) -> tuple[int, str]:
    result = run_process(args)
    if result.error is not None:
        return result.returncode, result.error
    return result.returncode, result.stdout or result.stderr


def _config_enabled(atuin: str, key: str) -> bool | None:
    code, value = _command([atuin, "config", "get", key, "--resolved"])
    if code != 0:
        return None

    normalized = value.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def inspect() -> Diagnostic:
    session_present = bool(os.environ.get("ATUIN_SESSION"))
    pty_proxy_active = bool(os.environ.get("ATUIN_PTY_PROXY_ACTIVE"))
    atuin_path = shutil.which("atuin")
    if atuin_path is None:
        return Diagnostic(
            session_present=session_present,
            pty_proxy_active=pty_proxy_active,
        )

    code, version = _command([atuin_path, "--version"])
    daemon_enabled = _config_enabled(atuin_path, "daemon.enabled")
    daemon_autostart = _config_enabled(atuin_path, "daemon.autostart")
    pty_proxy_enabled = _config_enabled(atuin_path, "pty_proxy.enabled")
    output_enabled = _config_enabled(atuin_path, "output.enabled")

    latest: HistoryEntry | None = None
    history_error: str | None = None
    if session_present:
        try:
            entries = recent_entries(1)
        except AtuinError as exc:
            history_error = str(exc)
        else:
            latest = entries[0] if entries else None

    # Finish CLI subprocesses before initializing gRPC background threads.
    daemon: DaemonInfo | None = None
    daemon_error: str | None = None
    try:
        daemon = daemon_info()
    except AtuinError as exc:
        daemon_error = str(exc)

    return Diagnostic(
        atuin_path=atuin_path,
        atuin_version=version if code == 0 else None,
        session_present=session_present,
        daemon_enabled=daemon_enabled,
        daemon_autostart=daemon_autostart,
        pty_proxy_enabled=pty_proxy_enabled,
        output_enabled=output_enabled,
        pty_proxy_active=pty_proxy_active,
        daemon=daemon,
        daemon_error=daemon_error,
        latest=latest,
        history_error=history_error,
    )


def _state(value: bool | None) -> str:
    if value is None:
        return "unavailable"
    return "yes" if value else "NO"


def _verification(result: Diagnostic) -> Verification:
    if result.atuin_path is None:
        return Verification(False, "Atuin is not on PATH")
    if not result.session_present:
        return Verification(False, "ATUIN_SESSION is not set")
    if result.output_enabled is not True:
        return Verification(False, "Atuin command-output capture is not enabled")
    if not result.pty_proxy_active:
        return Verification(False, "pty-proxy is not active in this shell")
    if result.history_error is not None:
        return Verification(False, result.history_error)
    if result.daemon is None:
        detail = f": {result.daemon_error}" if result.daemon_error else ""
        return Verification(False, f"cannot reach Atuin daemon{detail}")
    if not result.daemon.healthy:
        return Verification(False, "Atuin daemon is unhealthy")
    if result.latest is None:
        return Verification(False, "no current-session history")
    if result.latest.output_error:
        return Verification(False, result.latest.output_error)
    if result.latest.output is None:
        return Verification(False, "command output was not captured")
    return Verification(True, "PASS")


def _print_remediation() -> None:
    print("\nremediation:")
    print("  atuin config enable output-capture")
    print("\n  Follow Atuin's restart instructions, open a new shell, run a command, then run:")
    print("    copout verify")


def doctor() -> int:
    result = inspect()
    print("copout doctor")
    print(f"  atuin executable: {result.atuin_path or 'missing'}")
    if result.atuin_path is None:
        print("\ndiagnosis:\n  FAIL: Atuin is a required dependency and is not on PATH.")
        return 2

    print(f"  atuin version:    {result.atuin_version or 'unavailable'}")
    print(f"  shell session:    {'present' if result.session_present else 'MISSING'}")

    print("\nconfiguration:")
    print(f"  daemon.enabled:    {_state(result.daemon_enabled)}")
    print(f"  daemon.autostart:  {_state(result.daemon_autostart)}")
    print(f"  pty_proxy.enabled: {_state(result.pty_proxy_enabled)}")
    print(f"  output.enabled:    {_state(result.output_enabled)}")

    print("\nruntime:")
    print(f"  pty-proxy active:  {'yes' if result.pty_proxy_active else 'NO'}")
    if result.daemon is None:
        print("  jerakeen daemon:   NO")
        if result.daemon_error:
            print(f"    {result.daemon_error}")
    else:
        print(f"  jerakeen daemon:   {'yes' if result.daemon.healthy else 'UNHEALTHY'}")
        print(f"    target:           {result.daemon.description}")
        print(f"    atuin:            {result.daemon.version}")
        print(f"    protocol:         {result.daemon.protocol}")
        print(f"    pid:              {result.daemon.pid}")

    if result.latest is not None:
        print(f"  latest command:    {result.latest.command}")
        print(f"  latest status:     {result.latest.exit_status}")
        print(f"  captured output:   {'yes' if result.latest.output is not None else 'NO'}")

    if not result.session_present:
        print("\ndiagnosis:")
        print("  FAIL: ATUIN_SESSION is not set in this shell.")
        print("  Ensure normal `atuin init` shell integration is loaded, then open a new shell.")
        return 4

    if result.history_error is not None:
        print(f"\ndiagnosis:\n  FAIL: {result.history_error}")
        return 3

    if result.latest is None:
        print("\ndiagnosis:")
        print("  FAIL: Atuin returned no matching history entries for this session.")
        print("  Inspect `atuin history list --session` next.")
        return 4

    capture_configured = all(
        value is True
        for value in (
            result.daemon_enabled,
            result.pty_proxy_enabled,
            result.output_enabled,
        )
    )
    if not capture_configured:
        print("\ndiagnosis:")
        print("  PARTIAL: Atuin history works, but command-output capture is not fully configured.")
        _print_remediation()
        return 5

    if not result.pty_proxy_active:
        print("\ndiagnosis:")
        print("  PARTIAL: pty-proxy is configured but is not active in this shell.")
        print("  Initialize `atuin pty-proxy` before normal `atuin init` in the shell")
        print("  startup file, then open a new shell, run a command, and rerun `copout verify`.")
        return 5

    if result.daemon is None or not result.daemon.healthy:
        print("\ndiagnosis:")
        print("  PARTIAL: Atuin is configured for daemon operation, but Jerakeen")
        print("  could not connect to a healthy Atuin daemon.")
        print("  Open a new shell or inspect the Atuin daemon runtime.")
        return 5

    if result.latest.output_error:
        print(f"\ndiagnosis:\n  PARTIAL: {result.latest.output_error}")
        return 5

    if result.latest.output is None:
        print("\ndiagnosis:")
        print("  PARTIAL: output capture, pty-proxy, and the Atuin daemon are enabled,")
        print("  but command output was not captured for the latest command.")
        print("  Run a new command and rerun `copout verify`; if it still fails, inspect")
        print("  the pty-proxy capture path and OSC 133 shell markers.")
        return 5

    print("\ndiagnosis:")
    print("  PASS: Atuin history and Jerakeen daemon output are available to Copout.")
    return 0


def verify() -> int:
    verification = _verification(inspect())
    prefix = "copout verify: " if verification.ok else "copout verify: FAIL: "
    print(f"{prefix}{verification.message}")
    return 0 if verification.ok else 1
