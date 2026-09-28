from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from copout import clipboard


def _install_clipboard_helper(tmp_path: Path) -> Path:
    helper = tmp_path / "pbcopy"
    helper.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "payload = sys.stdin.read()\n"
        'Path(os.environ["CLIPBOARD_FILE"]).write_text(payload)\n'
    )
    helper.chmod(0o755)
    return helper


def test_writer_delivers_payload(monkeypatch, tmp_path: Path) -> None:
    marker = tmp_path / "clipboard.txt"
    _install_clipboard_helper(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("CLIPBOARD_FILE", str(marker))

    writer = clipboard.start_clipboard_writer()

    assert writer.write("payload") == 0
    assert marker.read_text() == "payload"


def test_abort_does_not_publish_empty_payload(monkeypatch, tmp_path: Path) -> None:
    marker = tmp_path / "clipboard.txt"
    _install_clipboard_helper(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("CLIPBOARD_FILE", str(marker))

    writer = clipboard.start_clipboard_writer()
    writer.abort()

    assert not marker.exists()


def test_writer_reports_encoding_failure(capsys) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
        text=True,
        encoding="ascii",
    )
    writer = clipboard.ClipboardWriter(process)

    assert writer.write("🍄") == 127
    assert "clipboard helper I/O failed" in capsys.readouterr().err
