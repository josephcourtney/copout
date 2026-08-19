from __future__ import annotations

from typing import Any, Self

import pytest

from copout.atuin import HistoryEntry, parse_history_result, parse_output_result, recent_entries
from copout.atuin_mcp import AtuinError, Tool, tool_arguments


class FakeContextClient:
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


def test_parse_history_structured_content() -> None:
    result = {
        "structuredContent": {
            "results": [
                {
                    "history_id": "abc",
                    "command": "false",
                    "cwd": "/tmp",
                    "exit_status": 1,
                    "duration": 0.04,
                    "timestamp": "2026-08-19T10:00:00Z",
                }
            ]
        }
    }
    assert parse_history_result(result) == [
        HistoryEntry(
            id="abc",
            command="false",
            cwd="/tmp",
            exit_status=1,
            duration=0.04,
            timestamp="2026-08-19T10:00:00Z",
        )
    ]


def test_parse_output_text_content() -> None:
    assert parse_output_result({"content": [{"type": "text", "text": "boom\n"}]}) == "boom\n"


def test_tool_arguments_adapt_to_schema() -> None:
    history = Tool(
        "atuin_history",
        {"properties": {"filter_mode": {}, "limit": {}, "failed_only": {}, "query": {}}},
    )
    assert tool_arguments(history, session=True, limit=4, failed_only=True) == {
        "filter_mode": "session",
        "limit": 4,
        "failed_only": True,
    }
    output = Tool("atuin_output", {"properties": {"history_id": {}}})
    assert tool_arguments(output, history_id="abc") == {"history_id": "abc"}


def test_tool_arguments_support_atuin_18_19_filter_modes() -> None:
    history = Tool(
        "atuin_history",
        {
            "properties": {
                "filter_modes": {"type": "array", "items": {"type": "string"}},
                "limit": {},
                "query": {},
            },
            "required": ["filter_modes"],
        },
    )
    assert tool_arguments(history, session=True, limit=8) == {
        "filter_modes": ["session"],
        "limit": 8,
    }


class FakeClient:
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None

    def tools(self) -> dict[str, Tool]:
        return {
            "atuin_history": Tool(
                "atuin_history",
                {"properties": {"limit": {}, "filter_mode": {}}},
            ),
            "atuin_output": Tool(
                "atuin_output",
                {"properties": {"history_id": {}}},
            ),
        }

    def call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if tool.name == "atuin_history":
            return {
                "structuredContent": {
                    "results": [
                        {
                            "history_id": "1",
                            "command": "echo one",
                            "timestamp": "2026-08-19T09:00:00Z",
                            "exit_status": 0,
                        },
                        {
                            "history_id": "2",
                            "command": "false",
                            "timestamp": "2026-08-19T10:00:00Z",
                            "exit_status": 1,
                        },
                    ]
                }
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"output-{arguments['history_id']}",
                }
            ]
        }


def test_recent_entries_fetches_output_and_sorts_newest_first() -> None:
    entries = recent_entries(2, client_factory=FakeClient)
    assert [entry.id for entry in entries] == ["2", "1"]
    assert [entry.output for entry in entries] == ["output-2", "output-1"]


def test_tool_arguments_only_sends_query_when_required() -> None:
    optional = Tool(
        "atuin_history",
        {
            "properties": {
                "query": {"type": "string"},
                "filter_modes": {"type": "array"},
                "limit": {},
            },
            "required": ["filter_modes"],
        },
    )
    assert "query" not in tool_arguments(optional, session=True, limit=4)

    required = Tool(
        "atuin_history",
        {
            "properties": {
                "query": {"type": "string"},
                "filter_modes": {"type": "array"},
            },
            "required": ["filter_modes", "query"],
        },
    )
    assert tool_arguments(required, session=True)["query"] == ""


def test_parse_atuin_18_19_history_text() -> None:
    result = {
        "content": [
            {
                "type": "text",
                "text": (
                    "## #1. (History ID: 0198cafe000070008000000000000001):\n"
                    "`false`\n"
                    "[2026-08-19 12:56:34] (in `/Users/josephcourtney`, exit 1), 71ms\n"
                    "\n"
                    "## #2. (History ID: 0198cafe000070008000000000000002):\n"
                    "`printf 'hello\\nworld\\n'`\n"
                    "[2026-08-19 12:55:00] (in `/tmp`, exit 0), 1.234s\n"
                ),
            }
        ]
    }
    entries = parse_history_result(result)
    assert entries == [
        HistoryEntry(
            id="0198cafe000070008000000000000001",
            command="false",
            cwd="/Users/josephcourtney",
            exit_status=1,
            duration=0.071,
            timestamp="2026-08-19 12:56:34",
        ),
        HistoryEntry(
            id="0198cafe000070008000000000000002",
            command="printf 'hello\\nworld\\n'",
            cwd="/tmp",
            exit_status=0,
            duration=1.234,
            timestamp="2026-08-19 12:55:00",
        ),
    ]


def test_parse_atuin_18_19_output_text() -> None:
    result = {
        "content": [
            {
                "type": "text",
                "text": (
                    "History ID: 0198cafe000070008000000000000001\n"
                    "Total output: 12 bytes, 2 lines\n"
                    "Selected output:\n"
                    "0\thello\n"
                    "1\tworld\n"
                ),
            }
        ]
    }
    assert parse_output_result(result) == "hello\nworld\n"


def test_parse_atuin_output_unavailable_and_empty() -> None:
    missing = {
        "content": [
            {
                "type": "text",
                "text": "No captured output found for history ID 0198cafe000070008000000000000001.",
            }
        ]
    }
    empty = {
        "content": [
            {
                "type": "text",
                "text": "Captured output for history ID 0198cafe000070008000000000000001 is empty.",
            }
        ]
    }
    assert parse_output_result(missing) is None
    assert parse_output_result(empty) == ""


class TextMCPClient(FakeContextClient):
    def tools(self):
        return {
            "atuin_history": Tool(
                "atuin_history",
                {
                    "properties": {
                        "query": {"type": "string"},
                        "filter_modes": {"type": "array"},
                        "limit": {},
                    },
                    "required": ["query", "filter_modes"],
                },
            ),
            "atuin_output": Tool("atuin_output", {"properties": {"history_id": {}}}),
        }

    def call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if tool.name == "atuin_history":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "## #1. (History ID: c0):\n"
                            "`copout verify`\n"
                            "[2026-08-19 12:58:01] (in `/tmp`, exit -1)\n\n"
                            "## #2. (History ID: f1):\n"
                            "`false`\n"
                            "[2026-08-19 12:58:00] (in `/tmp`, exit 1), 71ms\n"
                        ),
                    }
                ]
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"History ID: {arguments['history_id']}\n"
                        "Total output: 0 bytes, 0 lines\n"
                        "Selected output:\n"
                    ),
                }
            ]
        }


def test_recent_entries_parses_real_mcp_text_and_skips_copout() -> None:
    entries = recent_entries(1, client_factory=TextMCPClient)
    assert len(entries) == 1
    assert entries[0].id == "f1"
    assert entries[0].command == "false"
    assert entries[0].exit_status == 1
    assert entries[0].duration == 0.071


def test_parse_history_structured_duration_ms_is_normalized_to_seconds() -> None:
    result = {
        "structuredContent": {
            "results": [
                {
                    "history_id": "abc",
                    "command": "sleep 0.25",
                    "cwd": "/tmp",
                    "exit_status": 0,
                    "duration_ms": 250,
                    "timestamp": "2026-08-19T10:00:00Z",
                }
            ]
        }
    }

    assert parse_history_result(result) == [
        HistoryEntry(
            id="abc",
            command="sleep 0.25",
            cwd="/tmp",
            exit_status=0,
            duration=0.25,
            timestamp="2026-08-19T10:00:00Z",
        )
    ]


def test_parse_history_prefers_duration_seconds_over_duration_ms() -> None:
    result = {
        "structuredContent": {
            "results": [
                {
                    "history_id": "abc",
                    "command": "true",
                    "duration": 1.5,
                    "duration_ms": 9999,
                }
            ]
        }
    }

    entries = parse_history_result(result)

    assert len(entries) == 1
    assert entries[0].duration == 1.5


class SuccessfulHistoryClient(FakeContextClient):
    def tools(self):
        return {
            "atuin_history": Tool(
                "atuin_history",
                {
                    "properties": {
                        "filter_mode": {},
                        "limit": {},
                        "failed_only": {},
                    }
                },
            )
        }

    def call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        assert tool.name == "atuin_history"
        return {
            "structuredContent": {
                "results": [
                    {
                        "history_id": "success",
                        "command": "true",
                        "exit_status": 0,
                        "timestamp": "2026-08-19T10:00:00Z",
                    },
                    {
                        "history_id": "unknown",
                        "command": "echo unknown",
                        "exit_status": None,
                        "timestamp": "2026-08-19T09:59:00Z",
                    },
                ]
            }
        }


def test_recent_entries_failed_only_does_not_fall_back_to_successes() -> None:
    entries = recent_entries(
        5,
        failed_only=True,
        include_output=False,
        client_factory=SuccessfulHistoryClient,
    )

    assert entries == []


class MixedStatusHistoryClient(FakeContextClient):
    def tools(self):
        return {
            "atuin_history": Tool(
                "atuin_history",
                {
                    "properties": {
                        "filter_mode": {},
                        "limit": {},
                        "failed_only": {},
                    }
                },
            )
        }

    def call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        assert tool.name == "atuin_history"
        return {
            "structuredContent": {
                "results": [
                    {
                        "history_id": "success",
                        "command": "true",
                        "exit_status": 0,
                        "timestamp": "2026-08-19T10:00:02Z",
                    },
                    {
                        "history_id": "unknown",
                        "command": "echo unknown",
                        "timestamp": "2026-08-19T10:00:01Z",
                    },
                    {
                        "history_id": "failure",
                        "command": "false",
                        "exit_status": 1,
                        "timestamp": "2026-08-19T10:00:00Z",
                    },
                ]
            }
        }


def test_recent_entries_failed_only_excludes_success_and_unknown_status() -> None:
    entries = recent_entries(
        5,
        failed_only=True,
        include_output=False,
        client_factory=MixedStatusHistoryClient,
    )

    assert [entry.id for entry in entries] == ["failure"]
    assert entries[0].exit_status == 1


class OutputFailureClient(FakeContextClient):
    def tools(self):
        return {
            "atuin_history": Tool(
                "atuin_history",
                {"properties": {"filter_mode": {}, "limit": {}}},
            ),
            "atuin_output": Tool(
                "atuin_output",
                {"properties": {"history_id": {}}},
            ),
        }

    def call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if tool.name == "atuin_history":
            return {
                "structuredContent": {
                    "results": [
                        {
                            "history_id": "abc",
                            "command": "false",
                            "exit_status": 1,
                            "timestamp": "2026-08-19T10:00:00Z",
                        }
                    ]
                }
            }

        raise AtuinError("output transport failed")


def test_recent_entries_propagates_output_transport_failure() -> None:
    with pytest.raises(AtuinError, match="output transport failed"):
        recent_entries(1, client_factory=OutputFailureClient)


def test_recent_entries_can_skip_output_lookup() -> None:
    class HistoryOnlyClient(FakeContextClient):
        def tools(self):
            return {
                "atuin_history": Tool(
                    "atuin_history",
                    {"properties": {"filter_mode": {}, "limit": {}}},
                ),
                "atuin_output": Tool(
                    "atuin_output",
                    {"properties": {"history_id": {}}},
                ),
            }

        def call(
            self,
            tool: Tool,
            arguments: dict[str, Any],
        ) -> dict[str, Any]:
            if tool.name != "atuin_history":
                pytest.fail("output tool must not be called")

            return {
                "structuredContent": {
                    "results": [
                        {
                            "history_id": "abc",
                            "command": "echo hi",
                            "exit_status": 0,
                        }
                    ]
                }
            }

    entries = recent_entries(
        1,
        include_output=False,
        client_factory=HistoryOnlyClient,
    )

    assert len(entries) == 1
    assert entries[0].id == "abc"
    assert entries[0].output is None
