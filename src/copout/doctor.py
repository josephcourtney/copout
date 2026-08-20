from __future__ import annotations

import os
import shutil
import subprocess

from .atuin import AtuinError, daemon_info, recent_entries


def _command(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return result.returncode, (result.stdout or result.stderr).strip()


def doctor() -> int:
    print("copout doctor")
    atuin_path = shutil.which("atuin")
    print(f"  atuin executable: {atuin_path or 'missing'}")
    if not atuin_path:
        print("\ndiagnosis:\n  FAIL: Atuin is a required dependency and is not on PATH.")
        return 2

    code, version = _command([atuin_path, "--version"])
    print(f"  atuin version:    {version if code == 0 else 'unavailable'}")
    session = os.environ.get("ATUIN_SESSION", "")
    print(f"  shell session:    {'present' if session else 'MISSING'}")
    code, daemon = _command([atuin_path, "config", "get", "daemon", "--resolved"])
    print("  daemon config:    " + ("available" if code == 0 else "unavailable"))
    if code == 0 and daemon:
        for line in daemon.splitlines():
            print(f"    {line}")

    daemon_available = False
    try:
        info = daemon_info()
    except AtuinError as exc:
        print("  jerakeen daemon:  NO")
        print(f"    {exc}")
    else:
        daemon_available = info.healthy
        print(f"  jerakeen daemon:  {'yes' if info.healthy else 'UNHEALTHY'}")
        print(f"    target:          {info.description}")
        print(f"    atuin:           {info.version}")
        print(f"    protocol:        {info.protocol}")
        print(f"    pid:             {info.pid}")

    if not session:
        print("\ndiagnosis:")
        print("  FAIL: ATUIN_SESSION is not set in this shell.")
        print("  Ensure normal `atuin init` shell integration is loaded, then open a new shell.")
        return 4

    try:
        entries = recent_entries(1, include_output=daemon_available)
    except AtuinError as exc:
        print(f"\ndiagnosis:\n  FAIL: {exc}")
        return 3

    if not entries:
        print("\ndiagnosis:")
        print("  FAIL: Atuin returned no matching history entries for this session.")
        print("  Inspect `atuin history list --session` next.")
        return 4

    latest = entries[0]
    print(f"  latest command:   {latest.command}")
    print(f"  latest status:    {latest.exit_status}")
    print(f"  captured output:  {'yes' if latest.output is not None else 'NO'}")

    if not daemon_available:
        print("\ndiagnosis:")
        print("  PARTIAL: Atuin history works, but Jerakeen cannot reach the Atuin daemon.")
        print("  Enable the Atuin daemon and pty-proxy, then start a new shell.")
        return 5
    if latest.output is None:
        print("\ndiagnosis:")
        print("  PARTIAL: Atuin history works, but command output is unavailable.")
        print("  The daemon output cache is ephemeral; verify pty-proxy is active in this shell.")
        return 5

    print("\ndiagnosis:\n  PASS: Atuin history and Jerakeen daemon output are available to Copout.")
    return 0


def verify() -> int:
    return doctor()
