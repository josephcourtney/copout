from __future__ import annotations

from datetime import datetime
from typing import Literal, NotRequired, TypedDict

from . import context as context_capture
from .atuin import AtuinError, HistoryEntry, recent_entries
from .config import ContextOptions

SCHEMA_VERSION = 7

OutputState = Literal["captured", "unavailable"]
OutputSource = Literal["atuin-pty-proxy", "atuin-history-only"]


class ResultRecord(TypedDict):
    status: int | None


class OutputRecord(TypedDict):
    state: OutputState
    source: OutputSource
    text: str
    captured_bytes: int
    truncated: bool | None
    observed_bytes: int | None
    total_bytes: int | None
    error: str | None
    exit_capture_complete: NotRequired[bool]
    presentation_truncated: NotRequired[bool]
    presentation_omitted_bytes: NotRequired[int]


class ContextRecord(TypedDict):
    cwd: str
    git: NotRequired[context_capture.GitContext]


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
    environment: NotRequired[context_capture.EnvironmentContext]


class CommandRecord(RunRecord):
    version: int
    scope: Literal["command"]
    source: Literal["atuin"]
    captured_at: str
    environment: NotRequired[context_capture.EnvironmentContext]


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
    environment: NotRequired[context_capture.EnvironmentContext]


type CopoutRecord = CommandRecord | HistoryRecord


def _metadata(context_options: ContextOptions | None = None) -> CaptureMetadata:
    metadata: CaptureMetadata = {
        "version": SCHEMA_VERSION,
        "source": "atuin",
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if context_options is not None:
        environment = context_capture.capture_environment(context_options)
        if environment:
            metadata["environment"] = environment
    return metadata


def _entry_record(
    entry: HistoryEntry,
    context_options: ContextOptions | None = None,
) -> RunRecord:
    captured = entry.output is not None
    text = entry.output or ""
    output: OutputRecord = {
        "state": "captured" if captured else "unavailable",
        "error": entry.output_error,
        "source": "atuin-pty-proxy" if captured else "atuin-history-only",
        "text": text,
        "captured_bytes": len(text.encode()),
        "truncated": entry.output_truncated if captured else None,
        "observed_bytes": entry.output_observed_bytes if captured else None,
        "total_bytes": entry.output_total_bytes if captured else None,
    }
    if captured and entry.output_exit_capture_complete is not None:
        output["exit_capture_complete"] = entry.output_exit_capture_complete

    context: ContextRecord = {"cwd": entry.cwd}
    if context_options is not None:
        git = context_capture.capture_git_context(entry.cwd, context_options)
        if git:
            context["git"] = git

    return {
        "history_id": entry.id,
        "command": entry.command,
        "result": {"status": entry.exit_status},
        "output": output,
        "context": context,
        "timing": {"duration": entry.duration, "recorded_at": entry.timestamp},
    }


def build_record(*, context_options: ContextOptions | None = None) -> CommandRecord:
    entries = recent_entries(1)
    if not entries:
        raise AtuinError("no previous non-copout command found in the current Atuin session")

    return {
        **_entry_record(entries[0], context_options),
        **_metadata(context_options),
        "scope": "command",
    }


def build_history_from_entries(
    entries: list[HistoryEntry],
    *,
    requested: int | None = None,
    failed_only: bool = False,
    context_options: ContextOptions | None = None,
) -> HistoryRecord:
    """Build a chronological multi-run record from already selected entries."""
    runs = [_entry_record(entry, context_options) for entry in entries]
    return {
        **_metadata(context_options),
        "scope": "history",
        "runs": runs,
        "history": {
            "selected": len(runs),
            "requested": len(runs) if requested is None else requested,
            "failed_only": failed_only,
            "outputs_available": sum(run["output"]["state"] == "captured" for run in runs),
        },
    }


def build_history(
    *,
    count: int,
    failed_only: bool = False,
    context_options: ContextOptions | None = None,
) -> HistoryRecord:
    entries = recent_entries(count, failed_only=failed_only)
    entries.reverse()
    return build_history_from_entries(
        entries,
        requested=count,
        failed_only=failed_only,
        context_options=context_options,
    )
