"""Regression checks for the per-PTY Atuin session guard.

Tests here do not claim that live zsh/Atuin integration works on this host.
The actual session-identity and daemon-output check runs in test_live.py.
"""

from __future__ import annotations

import os

import pytest

from test_live import _clear_inherited_atuin_session, _extract_shell_session


def test_clearing_atuin_inheritance_does_not_touch_unrelated_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = (
        "ATUIN_SESSION",
        "ATUIN_SHLVL",
        "ATUIN_HISTORY_ID",
        "ATUIN_PTY_PROXY_ACTIVE",
        "ATUIN_PTY_PROXY_SOCKET",
    )
    for key in keys:
        monkeypatch.setenv(key, "parent-value")
    monkeypatch.setenv("ATUIN_SYNC_ADDRESS", "preserve")
    _clear_inherited_atuin_session()
    assert all(key not in os.environ for key in keys)
    assert os.environ["ATUIN_SYNC_ADDRESS"] == "preserve"


def test_session_identity_is_parsed_from_shell_output_not_echo() -> None:
    data = (
        b"print -r -- '__COPOUT_SESSION_''BEGIN__'\"$ATUIN_SESSION\""
        b"'__COPOUT_SESSION_''END__'\r\n"
        b"__COPOUT_SESSION_BEGIN__fresh-session-id__COPOUT_SESSION_END__\r\n"
    )
    assert _extract_shell_session(data, "parent-session-id") == "fresh-session-id"


def test_inherited_or_absent_shell_session_is_rejected() -> None:
    with pytest.raises(AssertionError, match="reused"):
        _extract_shell_session(
            b"__COPOUT_SESSION_BEGIN__same__COPOUT_SESSION_END__", "same"
        )
    with pytest.raises(AssertionError, match="did not initialize"):
        _extract_shell_session(b"not a session", "parent")
