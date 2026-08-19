from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstallResult:
    atuin_path: str
    daemon_configured: bool
    shell_file: Path | None
    pty_proxy_configured: bool
    changed_shell: bool


def _run(args: list[str]) -> bool:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _shell_info() -> tuple[str, Path | None, str | None]:
    shell = Path(os.environ.get("SHELL", "")).name
    home = Path.home()
    if shell == "zsh":
        return shell, home / ".zshrc", 'eval "$(atuin pty-proxy init zsh)"'
    if shell == "bash":
        return shell, home / ".bashrc", 'eval "$(atuin pty-proxy init bash)"'
    if shell == "fish":
        return (
            shell,
            home / ".config" / "fish" / "config.fish",
            "atuin pty-proxy init fish | source",
        )
    return shell, None, None


def _configure_pty_proxy(path: Path, line: str) -> tuple[bool, bool]:
    try:
        original = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return False, False
    if line in original:
        return True, False
    marker = "# copout: Atuin pty-proxy for command output capture"
    block = f"{marker}\n{line}\n"
    lines = original.splitlines(keepends=True)
    insert_at = 0
    for index, existing in enumerate(lines):
        if "atuin init" in existing and "pty-proxy" not in existing:
            insert_at = index
            break
    else:
        insert_at = len(lines)
    if insert_at == len(lines) and original and not original.endswith("\n"):
        original += "\n"
        lines = original.splitlines(keepends=True)
    lines.insert(insert_at, block)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return False, False
    return True, True


def install() -> InstallResult:
    atuin_path = shutil.which("atuin")
    if atuin_path is None:
        raise RuntimeError("Atuin is required; install Atuin and ensure `atuin` is on PATH")
    daemon_ok = _run([atuin_path, "config", "set", "daemon.enabled", "true"])
    daemon_ok = _run([atuin_path, "config", "set", "daemon.autostart", "true"]) and daemon_ok
    _shell, shell_file, pty_line = _shell_info()
    pty_ok = False
    changed = False
    if shell_file is not None and pty_line is not None:
        pty_ok, changed = _configure_pty_proxy(shell_file, pty_line)
    return InstallResult(
        atuin_path=atuin_path,
        daemon_configured=daemon_ok,
        shell_file=shell_file,
        pty_proxy_configured=pty_ok,
        changed_shell=changed,
    )
