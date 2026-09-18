from __future__ import annotations

from dataclasses import replace

import pytest

from copout import atuin
from copout._process import ProcessResult
from copout.atuin import AtuinError, DaemonInfo, HistoryEntry, daemon_info, recent_entries


def test_parse_history_list_preserves_multiline_command() -> None:
    sep = "\x1f"
    raw = (
        sep.join(
            (
                "0198cafe-0000-7000-8000-000000000001",
                "2026-08-19 12:56:34",
                "/Users/josephcourtney/code",
                "1",
                "71ms",
                "printf 'hello\\nworld\\n'\nsecond line",
            )
        )
        + "\0"
    )

    entries = atuin._parse_history_list(raw)
    assert len(entries) == 1
    assert entries[0].duration == pytest.approx(0.071)
    assert [replace(entries[0], duration=None)] == [
        HistoryEntry(
            id="0198cafe-0000-7000-8000-000000000001",
            command="printf 'hello\\nworld\\n'\nsecond line",
            cwd="/Users/josephcourtney/code",
            exit_status=1,
            timestamp="2026-08-19 12:56:34",
        )
    ]


def test_parse_history_list_rejects_unrecognized_record() -> None:
    with pytest.raises(AtuinError, match="unrecognized format"):
        atuin._parse_history_list("only one field\0")


def test_load_history_uses_documented_history_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATUIN_SESSION", "session")
    monkeypatch.setattr(atuin.shutil, "which", lambda executable: "/usr/bin/atuin")
    captured: list[list[str]] = []

    def run(args: list[str], *, timeout: float) -> ProcessResult:
        assert timeout == 5
        captured.append(args)
        return ProcessResult(
            0,
            "id\x1f2026-08-19 10:00:00\x1f/tmp\x1f0\x1f2ms\x1fecho hi\0",
            "",
        )

    monkeypatch.setattr(atuin, "run_process", run)

    assert atuin._load_history() == [
        HistoryEntry("id", "echo hi", "/tmp", 0, 0.002, "2026-08-19 10:00:00")
    ]
    args = captured[0]
    assert args[:4] == ["/usr/bin/atuin", "history", "list", "--session"]
    assert "--print0" in args
    assert "--reverse=false" in args
    assert "--format" in args
    assert "mcp" not in args


def test_load_history_requires_shell_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATUIN_SESSION", raising=False)
    monkeypatch.setattr(atuin.shutil, "which", lambda executable: "/usr/bin/atuin")

    with pytest.raises(AtuinError, match="ATUIN_SESSION"):
        atuin._load_history()


def test_recent_entries_filters_copout_preserves_order_and_fetches_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [
        HistoryEntry("3", "copout -p", "/tmp", 0, 0.1, "2026-08-19 11:00:00"),
        HistoryEntry("2", "false", "/tmp", 1, 0.2, "2026-08-19 10:00:00"),
        HistoryEntry("1", "echo one", "/tmp", 0, 0.1, "2026-08-19 09:00:00"),
    ]
    calls: list[list[str]] = []

    async def add_outputs(selected: list[HistoryEntry]) -> list[HistoryEntry]:
        calls.append([entry.id for entry in selected])
        outputs = {"2": "failed\n", "1": "one\n"}
        return [replace(entry, output=outputs.get(entry.id)) for entry in selected]

    monkeypatch.setattr(atuin, "_load_history", lambda: entries)
    monkeypatch.setattr(atuin, "_add_outputs", add_outputs)

    result = recent_entries(2)

    assert [entry.id for entry in result] == ["2", "1"]
    assert [entry.output for entry in result] == ["failed\n", "one\n"]
    assert calls == [["2", "1"]]


def test_recent_entries_failed_only_filters_before_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        HistoryEntry("3", "exit 2", exit_status=2, timestamp="2026-08-19 11:00:00"),
        HistoryEntry("2", "true", exit_status=0, timestamp="2026-08-19 10:00:00"),
        HistoryEntry("1", "false", exit_status=1, timestamp="2026-08-19 09:00:00"),
    ]
    monkeypatch.setattr(atuin, "_load_history", lambda: entries)

    result = recent_entries(1, failed_only=True, include_output=False)

    assert [entry.id for entry in result] == ["3"]


def test_recent_entries_degrades_to_history_when_output_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = HistoryEntry("1", "echo hi", timestamp="2026-08-19 09:00:00")

    async def fail_outputs(selected: list[HistoryEntry]) -> list[HistoryEntry]:
        del selected
        raise RuntimeError("daemon unavailable")

    monkeypatch.setattr(atuin, "_load_history", lambda: [entry])
    monkeypatch.setattr(atuin, "_add_outputs", fail_outputs)

    assert recent_entries(1) == [replace(entry, output_error="RuntimeError: daemon unavailable")]


def test_daemon_info_runs_async_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = DaemonInfo(
        description="unix:/tmp/atuin.sock",
        healthy=True,
        version="18.19.0",
        pid=123,
        protocol=1,
    )

    async def load_info() -> DaemonInfo:
        return expected

    monkeypatch.setattr(atuin, "_daemon_info", load_info)
    assert daemon_info() == expected


def test_daemon_info_normalizes_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_connect(*, timeout: float) -> object:
        del timeout
        raise RuntimeError("no socket")

    monkeypatch.setattr(atuin, "connect", fail_connect)

    with pytest.raises(AtuinError, match="Jerakeen could not connect"):
        daemon_info()
