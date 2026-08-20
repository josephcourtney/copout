from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from copout import atuin
from copout.atuin import AtuinError, DaemonInfo, HistoryEntry, daemon_info, recent_entries


@dataclass(frozen=True)
class FakeOutput:
    text: str


@dataclass(frozen=True)
class FakeStatus:
    healthy: bool = True
    version: str = "18.19.0"
    pid: int = 123
    protocol: int = 1


class FakeSemantic:
    def __init__(self, outputs: dict[str, str | None]) -> None:
        self.outputs = outputs
        self.calls: list[str] = []

    async def output(self, history_id: str) -> FakeOutput | None:
        self.calls.append(history_id)
        value = self.outputs.get(history_id)
        return None if value is None else FakeOutput(value)


class FakeClient:
    description = "unix:/tmp/atuin.sock"

    def __init__(self, outputs: dict[str, str | None] | None = None) -> None:
        self.semantic = FakeSemantic(outputs or {})

    async def status(self) -> FakeStatus:
        return FakeStatus()


class FakeContext:
    def __init__(self, client: FakeClient) -> None:
        self.client = client

    async def __aenter__(self) -> FakeClient:
        return self.client

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


class FakeConnect:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.timeouts: list[float] = []

    def __call__(self, *, timeout: float) -> FakeContext:
        self.timeouts.append(timeout)
        return FakeContext(self.client)


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

    assert atuin._parse_history_list(raw) == [
        HistoryEntry(
            id="0198cafe-0000-7000-8000-000000000001",
            command="printf 'hello\\nworld\\n'\nsecond line",
            cwd="/Users/josephcourtney/code",
            exit_status=1,
            duration=0.071,
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

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            "id\x1f2026-08-19 10:00:00\x1f/tmp\x1f0\x1f2ms\x1fecho hi\0",
            "",
        )

    monkeypatch.setattr(atuin.subprocess, "run", run)

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


def test_recent_entries_filters_copout_sorts_and_fetches_output() -> None:
    entries = [
        HistoryEntry("3", "copout -p", "/tmp", 0, 0.1, "2026-08-19 11:00:00"),
        HistoryEntry("2", "false", "/tmp", 1, 0.2, "2026-08-19 10:00:00"),
        HistoryEntry("1", "echo one", "/tmp", 0, 0.1, "2026-08-19 09:00:00"),
    ]
    client = FakeClient({"2": "failed\n", "1": "one\n"})
    connect = FakeConnect(client)

    result = recent_entries(
        2,
        history_loader=lambda: entries,
        connect_factory=connect,
    )

    assert [entry.id for entry in result] == ["2", "1"]
    assert [entry.output for entry in result] == ["failed\n", "one\n"]
    assert client.semantic.calls == ["2", "1"]
    assert connect.timeouts == [3.0]


def test_recent_entries_failed_only_filters_before_limit() -> None:
    entries = [
        HistoryEntry("3", "exit 2", exit_status=2, timestamp="2026-08-19 11:00:00"),
        HistoryEntry("2", "true", exit_status=0, timestamp="2026-08-19 10:00:00"),
        HistoryEntry("1", "false", exit_status=1, timestamp="2026-08-19 09:00:00"),
    ]

    result = recent_entries(
        1,
        failed_only=True,
        include_output=False,
        history_loader=lambda: entries,
    )

    assert [entry.id for entry in result] == ["3"]


def test_recent_entries_degrades_to_history_when_jerakeen_is_unavailable() -> None:
    entry = HistoryEntry("1", "echo hi", timestamp="2026-08-19 09:00:00")

    def fail_connect(*, timeout: float) -> FakeContext:
        del timeout
        raise RuntimeError("daemon unavailable")

    assert recent_entries(
        1,
        history_loader=lambda: [entry],
        connect_factory=fail_connect,
    ) == [entry]


def test_daemon_info_comes_from_jerakeen() -> None:
    info = daemon_info(connect_factory=FakeConnect(FakeClient()))

    assert info == DaemonInfo(
        description="unix:/tmp/atuin.sock",
        healthy=True,
        version="18.19.0",
        pid=123,
        protocol=1,
    )


def test_daemon_info_normalizes_connection_errors() -> None:
    def fail_connect(*, timeout: float) -> FakeContext:
        del timeout
        raise RuntimeError("no socket")

    with pytest.raises(AtuinError, match="Jerakeen could not connect"):
        daemon_info(connect_factory=fail_connect)
