from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Self

from .atuin_mcp import AtuinError, MCPClient, Tool, find_tool, tool_arguments


class MCPClientLike(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...

    def tools(self) -> dict[str, Tool]: ...

    def call(self, tool: Tool, arguments: dict[str, Any]) -> dict[str, Any]: ...


ClientFactory = Callable[[], MCPClientLike]


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    command: str
    cwd: str = ""
    exit_status: int | None = None
    duration: float | None = None
    timestamp: str = ""
    output: str | None = None


_HISTORY_HEADER_RE = re.compile(r"^## #\d+\. \(History ID: ([^)]+)\):$", re.MULTILINE)
_HISTORY_META_RE = re.compile(
    r"^\[(?P<timestamp>[^]]+)\] \(in `(?P<cwd>.*)`, exit (?P<exit>-?\d+)\)"
    r"(?:, (?P<duration>[^—]+?))?(?: — .*)?$"
)
_OUTPUT_LINE_RE = re.compile(r"^\s*\d+\t")


def _duration_seconds(text: str | None) -> float | None:
    if text is None:
        return None
    value = text.strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(ns|µs|us|ms|s|m|h)", value)
    if match is None:
        return None
    amount = float(match.group(1))
    unit = match.group(2)
    if unit == "ns":
        return amount / 1_000_000_000
    if unit in {"µs", "us"}:
        return amount / 1_000_000
    if unit == "ms":
        return amount / 1_000
    if unit == "s":
        return amount
    if unit == "m":
        return amount * 60
    return amount * 3600


def _parse_history_text(text: str) -> list[HistoryEntry]:
    headers = list(_HISTORY_HEADER_RE.finditer(text))
    entries: list[HistoryEntry] = []
    for index, header in enumerate(headers):
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[start:end].strip("\n")
        lines = body.splitlines()
        if len(lines) < 2:
            continue
        meta_index = None
        meta_match = None
        for i in range(len(lines) - 1, -1, -1):
            candidate = _HISTORY_META_RE.match(lines[i])
            if candidate is not None:
                meta_index = i
                meta_match = candidate
                break
        if meta_index is None or meta_match is None:
            continue
        command_block = "\n".join(lines[:meta_index]).strip()
        if (
            command_block.startswith("`")
            and command_block.endswith("`")
            and len(command_block) >= 2
        ):
            command_block = command_block[1:-1]
        if not command_block:
            continue
        entries.append(
            HistoryEntry(
                id=header.group(1),
                command=command_block,
                cwd=meta_match.group("cwd"),
                exit_status=_int(meta_match.group("exit")),
                duration=_duration_seconds(meta_match.group("duration")),
                timestamp=meta_match.group("timestamp"),
            )
        )
    return entries


def _parse_output_text(text: str) -> str | None:
    stripped = text.strip("\n")
    if stripped.startswith("No captured output found for history ID "):
        return None
    if stripped.startswith("Captured output for history ID ") and stripped.endswith(" is empty."):
        return ""
    marker = "Selected output:\n"
    if marker not in text:
        return text or None
    selected = text.split(marker, 1)[1]
    lines = selected.splitlines(keepends=True)
    cleaned: list[str] = []
    for line in lines:
        if line.startswith("[...skipped "):
            cleaned.append(line)
            continue
        cleaned.append(_OUTPUT_LINE_RE.sub("", line, count=1))
    return "".join(cleaned)


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text_content(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _structured(result: dict[str, Any]) -> Any:
    for key in ("structuredContent", "structured_content"):
        if key in result:
            return result[key]
    text = _text_content(result).strip()
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return None


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _entry_from_mapping(item: dict[str, Any]) -> HistoryEntry | None:
    command = item.get("command") or item.get("cmd") or item.get("command_line")
    history_id = item.get("history_id") or item.get("historyId") or item.get("id")
    if not isinstance(command, str) or not command.strip() or history_id is None:
        return None

    status = item.get("exit")
    if status is None:
        status = item.get("exit_status")
    if status is None:
        status = item.get("status")

    duration = _float(item.get("duration"))
    if duration is None:
        duration_ms = _float(item.get("duration_ms"))
        duration = None if duration_ms is None else duration_ms / 1_000

    timestamp = item.get("timestamp") or item.get("time") or item.get("started_at") or ""
    cwd = item.get("cwd") or item.get("directory") or ""

    return HistoryEntry(
        id=str(history_id),
        command=command,
        cwd=str(cwd),
        exit_status=_int(status),
        duration=duration,
        timestamp=str(timestamp),
    )


def parse_history_result(result: dict[str, Any]) -> list[HistoryEntry]:
    structured = _structured(result)
    entries: list[HistoryEntry] = []
    seen: set[str] = set()
    for item in _walk_dicts(structured):
        entry = _entry_from_mapping(item)
        if entry is not None and entry.id not in seen:
            seen.add(entry.id)
            entries.append(entry)
    if entries:
        return entries
    text = _text_content(result)
    return _parse_history_text(text) if text else []


def parse_output_result(result: dict[str, Any]) -> str | None:
    direct_text = _text_content(result)
    structured_content = result.get("structuredContent", result.get("structured_content"))
    if structured_content is None and direct_text:
        return _parse_output_text(direct_text)
    structured = _structured(result)
    if isinstance(structured, str):
        return _parse_output_text(structured)
    if isinstance(structured, dict):
        for key in ("output", "text", "content", "stdout"):
            value = structured.get(key)
            if isinstance(value, str):
                return value
    return _parse_output_text(direct_text) if direct_text else None


def _is_copout_command(command: str) -> bool:
    words = re.split(r"\s+", command.strip())
    if not words:
        return False
    executable = words[0].rsplit("/", 1)[-1]
    return executable == "copout"


def _timestamp_key(entry: HistoryEntry) -> tuple[int, str]:
    text = entry.timestamp
    if not text:
        return (0, entry.id)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return (int(parsed.timestamp() * 1_000_000), entry.id)
    except ValueError:
        return (0, text + entry.id)


def recent_entries(
    count: int,
    *,
    failed_only: bool = False,
    include_output: bool = True,
    client_factory: ClientFactory = MCPClient,
) -> list[HistoryEntry]:
    requested = max(count, 1)

    with client_factory() as client:
        tools = client.tools()
        history_tool = find_tool(tools, "history")
        if history_tool is None:
            msg = "Atuin MCP server does not expose a history search tool"
            raise AtuinError(msg)
        result = client.call(
            history_tool,
            tool_arguments(
                history_tool,
                session=True,
                limit=max(requested * 4, 16),
                failed_only=failed_only,
            ),
        )
        entries = [
            entry for entry in parse_history_result(result) if not _is_copout_command(entry.command)
        ]

        if failed_only:
            entries = [
                entry
                for entry in entries
                if entry.exit_status is not None and entry.exit_status != 0
            ]

        entries.sort(key=_timestamp_key, reverse=True)
        entries = entries[:requested]

        output_tool = find_tool(tools, "output") if include_output else None
        if output_tool is None:
            return entries
        populated: list[HistoryEntry] = []
        for entry in entries:
            output_result = client.call(
                output_tool,
                tool_arguments(output_tool, history_id=entry.id),
            )
            output = parse_output_result(output_result)

            populated.append(
                HistoryEntry(
                    id=entry.id,
                    command=entry.command,
                    cwd=entry.cwd,
                    exit_status=entry.exit_status,
                    duration=entry.duration,
                    timestamp=entry.timestamp,
                    output=output,
                )
            )
        return populated


def previous_entry(*, client_factory: ClientFactory = MCPClient) -> HistoryEntry:
    entries = recent_entries(1, client_factory=client_factory)
    if entries:
        return entries[0]
    raise AtuinError("no previous non-copout command found in the current Atuin session")
