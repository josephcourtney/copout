from __future__ import annotations

import shutil
import subprocess
import sys


class ClipboardStartError(RuntimeError):
    """Clipboard helper could not be started."""


class ClipboardWriter:
    """A pre-started clipboard helper that accepts one rendered payload."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._finished = False

    def write(self, text: str) -> int:
        if self._finished:
            msg = "clipboard writer has already finished"
            raise RuntimeError(msg)

        try:
            self._process.communicate(text)
        except OSError as exc:
            self.abort()
            print(f"copout: clipboard helper I/O failed: {exc}", file=sys.stderr)
            return 127

        self._finished = True
        returncode = self._process.returncode
        if returncode is None:
            returncode = self._process.wait()
        if returncode != 0:
            print(f"copout: clipboard helper exited with status {returncode}", file=sys.stderr)
        return int(returncode)

    def abort(self) -> None:
        """Stop the helper without writing a clipboard payload."""
        if self._finished:
            return
        self._finished = True

        if self._process.poll() is None:
            try:
                self._process.terminate()
            except OSError:
                pass

        try:
            self._process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                self._process.kill()
            except OSError:
                pass
            self._process.communicate()


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


def start_clipboard_writer() -> ClipboardWriter:
    command = clipboard_command()
    if command is None:
        msg = "no clipboard helper found (tried pbcopy, wl-copy, xclip, xsel); use --print"
        raise ClipboardStartError(msg)

    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True)
    except OSError as exc:
        raise ClipboardStartError(f"failed to start clipboard helper: {exc}") from exc
    return ClipboardWriter(process)
