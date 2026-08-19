from __future__ import annotations

from pathlib import Path

from copout import installer


def test_configure_pty_proxy_inserts_before_atuin_init(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text('export FOO=1\neval "$(atuin init zsh)"\n', encoding="utf-8")
    ok, changed = installer._configure_pty_proxy(rc, 'eval "$(atuin pty-proxy init zsh)"')
    assert ok and changed
    text = rc.read_text(encoding="utf-8")
    assert text.index("pty-proxy init zsh") < text.index("atuin init zsh")


def test_configure_pty_proxy_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    line = 'eval "$(atuin pty-proxy init zsh)"'
    rc.write_text(line + "\n", encoding="utf-8")
    assert installer._configure_pty_proxy(rc, line) == (True, False)
