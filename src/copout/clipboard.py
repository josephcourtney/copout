from __future__ import annotations

import shutil
import subprocess
import sys


def clipboard_command() -> list[str] | None:
    candidates = (
        ("pbcopy", ["pbcopy"]),
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
    )
    for executable, command in candidates:
        if shutil.which(executable):
            return command
    return None


def copy_to_clipboard(text: str) -> int:
    command = clipboard_command()
    if command is None:
        print(
            "copout: no clipboard helper found (tried pbcopy, wl-copy, xclip, xsel); use --print",
            file=sys.stderr,
        )
        return 127
    try:
        proc = subprocess.run(command, input=text, text=True, check=False)
    except OSError as exc:
        print(f"copout: failed to start clipboard helper: {exc}", file=sys.stderr)
        return 127
    if proc.returncode != 0:
        print(f"copout: clipboard helper exited with status {proc.returncode}", file=sys.stderr)
    return int(proc.returncode)
