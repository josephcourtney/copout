from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict

from .atuin import AtuinError, HistoryEntry, recent_entries

SCHEMA_VERSION = 4

OutputState = Literal["captured", "unavailable"]
OutputSource = Literal["atuin-pty-proxy", "atuin-history-only"]


class ResultRecord(TypedDict):
    status: int | None


class OutputRecord(TypedDict):
    state: OutputState
    source: OutputSource
    text: str
    utf8_bytes: int
    truncated: bool | None
    observed_bytes: int | None
    total_bytes: int | None
    error: str | None


class ContextRecord(TypedDict):
    cwd: str


class TimingRecord(TypedDict):
    duration: float | None
    recorded_at: str


class RunRecord(TypedDict):
    history_id: str
    command: str
    result: ResultRecord
    output: OutputRecord
    context: ContextRecord
    timing: TimingRecord


class CaptureMetadata(TypedDict):
    version: int
    source: Literal["atuin"]
    captured_at: str


class CommandRecord(RunRecord):
    version: int
    scope: Literal["command"]
    source: Literal["atuin"]
    captured_at: str


class HistorySummary(TypedDict):
    selected: int
    requested: int
    failed_only: bool
    outputs_available: int


class HistoryRecord(TypedDict):
    version: int
    scope: Literal["history"]
    source: Literal["atuin"]
    runs: list[RunRecord]
    history: HistorySummary
    captured_at: str


type CopoutRecord = CommandRecord | HistoryRecord


def _metadata() -> CaptureMetadata:
    return {
        "version": SCHEMA_VERSION,
        "source": "atuin",
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _entry_record(entry: HistoryEntry) -> RunRecord:
    captured = entry.output is not None
    text = entry.output or ""
    return {
        "history_id": entry.id,
        "command": entry.command,
        "result": {"status": entry.exit_status},
        "output": {
            "state": "captured" if captured else "unavailable",
            "error": entry.output_error,
            "source": "atuin-pty-proxy" if captured else "atuin-history-only",
            "text": text,
            "utf8_bytes": len(text.encode()),
            "truncated": entry.output_truncated if captured else None,
            "observed_bytes": entry.output_observed_bytes if captured else None,
            "total_bytes": entry.output_total_bytes if captured else None,
        },
        "context": {"cwd": entry.cwd},
        "timing": {"duration": entry.duration, "recorded_at": entry.timestamp},
    }


def build_record() -> CommandRecord:
    entries = recent_entries(1)
    if not entries:
        raise AtuinError("no previous non-copout command found in the current Atuin session")

    return {
        **_entry_record(entries[0]),
        **_metadata(),
        "scope": "command",
    }


def build_history(*, count: int, failed_only: bool = False) -> HistoryRecord:
    entries = recent_entries(count, failed_only=failed_only)
    entries.reverse()
    runs = [_entry_record(entry) for entry in entries]
    return {
        **_metadata(),
        "scope": "history",
        "runs": runs,
        "history": {
            "selected": len(runs),
            "requested": count,
            "failed_only": failed_only,
            "outputs_available": sum(run["output"]["state"] == "captured" for run in runs),
        },
    }
