from __future__ import annotations

import os
import shutil
import subprocess

from .atuin import AtuinError, recent_entries
from .atuin_mcp import MCPClient, find_tool


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

    try:
        with MCPClient() as client:
            tools = client.tools()
            history_tool = find_tool(tools, "history")
            output_tool = find_tool(tools, "output")
            print(f"  history tool:     {'yes' if history_tool else 'NO'}")
            print(f"  output tool:      {'yes' if output_tool else 'NO'}")
        entries = recent_entries(1)
    except AtuinError as exc:
        print(f"\ndiagnosis:\n  FAIL: {exc}")
        return 3

    if not entries:
        print("\ndiagnosis:")
        if not session:
            print("  FAIL: ATUIN_SESSION is not set in this shell.")
            print(
                "  Ensure normal `atuin init` shell integration is loaded, then open a new shell."
            )
        else:
            print("  FAIL: Atuin returned no matching history entries for this session.")
            print(
                "  The MCP connection is healthy; inspect `atuin search --filter-mode session` next."
            )
        return 4
    latest = entries[0]
    print(f"  latest command:   {latest.command}")
    print(f"  latest status:    {latest.exit_status}")
    print(f"  captured output:  {'yes' if latest.output is not None else 'NO'}")
    if latest.output is None:
        print("\ndiagnosis:")
        print("  PARTIAL: Atuin history works, but command output is unavailable.")
        print("  Enable the Atuin daemon and pty-proxy, then start a new shell.")
        return 5
    print(
        "\ndiagnosis:\n  PASS: Atuin history and pty-proxy command output are available to Copout."
    )
    return 0


def verify() -> int:
    return doctor()
