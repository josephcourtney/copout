from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from copout import atuin_mcp
from copout.atuin_mcp import AtuinError, MCPClient


class FakeThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon
        self.started = False

    def start(self) -> None:
        self.started = True


class FakeProcess:
    def __init__(self) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def wait(self, *, timeout: float) -> int:
        self.wait_calls += 1
        return 0


def test_enter_closes_process_when_initialize_fails(monkeypatch) -> None:
    proc = FakeProcess()

    monkeypatch.setattr(atuin_mcp.shutil, "which", lambda executable: "/usr/bin/atuin")
    monkeypatch.setattr(atuin_mcp.subprocess, "Popen", lambda *args, **kwargs: proc)
    monkeypatch.setattr(atuin_mcp.threading, "Thread", FakeThread)

    def fail_initialize(self) -> None:
        raise AtuinError("initialize failed")

    monkeypatch.setattr(MCPClient, "_initialize", fail_initialize)

    client = MCPClient()

    with pytest.raises(AtuinError, match="initialize failed"):
        client.__enter__()

    assert proc.stdin.closed
    assert proc.terminate_calls == 1
    assert proc.wait_calls == 1
    assert client._proc is None


def test_close_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MCPClient()
    proc = FakeProcess()

    monkeypatch.setattr(client, "_proc", proc)

    client.close()
    client.close()

    assert proc.terminate_calls == 1
    assert proc.wait_calls == 1
    assert client._proc is None


def test_request_matches_response_by_json_rpc_id(monkeypatch) -> None:
    client = MCPClient(timeout=1.0)
    sent: list[dict[str, object]] = []

    monkeypatch.setattr(client, "_send", sent.append)

    client._responses.put(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "result": {"wrong": True},
        }
    )
    client._responses.put(
        {
            "jsonrpc": "2.0",
            "method": "notifications/example",
        }
    )
    client._responses.put(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"correct": True},
        }
    )

    result = client._request("example")

    assert result == {"correct": True}
    assert sent == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "example",
        }
    ]

    # Messages for other requests/notifications must not be lost.
    deferred = [
        client._responses.get_nowait(),
        client._responses.get_nowait(),
    ]

    assert deferred == [
        {
            "jsonrpc": "2.0",
            "id": 99,
            "result": {"wrong": True},
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/example",
        },
    ]


def test_request_wraps_non_mapping_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MCPClient(timeout=1.0)

    monkeypatch.setattr(client, "_send", lambda payload: None)

    client._responses.put(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": ["one", "two"],
        }
    )

    assert client._request("example") == {"value": ["one", "two"]}


def test_request_raises_for_mcp_error(monkeypatch) -> None:
    client = MCPClient(timeout=1.0)

    monkeypatch.setattr(client, "_send", lambda payload: None)
    client._responses.put(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32601,
                "message": "method not found",
            },
        }
    )

    with pytest.raises(AtuinError, match="method not found"):
        client._request("missing/method")


def test_request_timeout_is_reported_as_atuin_error(monkeypatch) -> None:
    client = MCPClient(timeout=0.0)

    monkeypatch.setattr(client, "_send", lambda payload: None)

    with pytest.raises(
        AtuinError,
        match=r"timed out waiting for Atuin MCP method tools/list",
    ):
        client._request("tools/list")


def test_read_stdout_ignores_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MCPClient()

    monkeypatch.setattr(
        client,
        "_proc",
        SimpleNamespace(
            stdout=io.StringIO('not-json\n\n{"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n')
        ),
    )

    client._read_stdout()

    assert client._responses.get_nowait() == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"ok": True},
    }
    assert client._responses.empty()


def test_read_stdout_ignores_non_object_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MCPClient()

    monkeypatch.setattr(
        client,
        "_proc",
        SimpleNamespace(
            stdout=io.StringIO(
                '["valid", "json", "but", "not", "an", "object"]\n'
                '{"jsonrpc":"2.0","id":1,"result":{}}\n'
            )
        ),
    )

    client._read_stdout()

    assert client._responses.get_nowait()["id"] == 1
    assert client._responses.empty()


def test_initialize_falls_back_between_supported_protocol_versions(
    monkeypatch,
) -> None:
    client = MCPClient()

    requests: list[tuple[str, dict[str, object]]] = []
    notifications: list[str] = []

    def request(method: str, params=None):
        assert params is not None
        requests.append((method, params))

        if len(requests) < 3:
            raise AtuinError("unsupported protocol")

        return {}

    def notify(method: str, params=None) -> None:
        notifications.append(method)

    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr(client, "_notify", notify)

    client._initialize()

    assert [params["protocolVersion"] for _method, params in requests] == [
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
    ]

    assert notifications == ["notifications/initialized"]


def test_initialize_raises_last_protocol_error(monkeypatch) -> None:
    client = MCPClient()

    attempts = 0

    def request(method: str, params=None):
        nonlocal attempts
        attempts += 1
        raise AtuinError(f"unsupported protocol attempt {attempts}")

    monkeypatch.setattr(client, "_request", request)

    with pytest.raises(
        AtuinError,
        match="unsupported protocol attempt 3",
    ):
        client._initialize()

    assert attempts == 3
