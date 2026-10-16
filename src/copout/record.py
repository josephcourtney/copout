from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, NotRequired, TypedDict

from . import context as context_capture
from .atuin import AtuinError, HistoryEntry, hydrate_outputs, recent_history
from .config import ContextOptions

SCHEMA_VERSION = 9

OutputState = Literal["captured", "unavailable"]
OutputSource = Literal["atuin-pty-proxy", "atuin-history-only"]
OutputCompleteness = Literal["unknown", "incomplete", "unavailable"]


class ResultRecord(TypedDict):
    status: int | None


class OutputRecord(TypedDict):
    state: OutputState
    source: OutputSource
    text: str
    captured_bytes: int
    presented_bytes: int
    completeness: OutputCompleteness
    coverage_warning: NotRequired[str]
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


class CopoutRecord(TypedDict):
    version: int
    source: Literal["atuin"]
    captured_at: str
    runs: list[RunRecord]
    environment: NotRequired[context_capture.EnvironmentContext]


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Current context observed before command-output retrieval starts."""

    environment: context_capture.EnvironmentContext
    git_by_cwd: dict[str, context_capture.GitContext | None]


def _metadata(environment: context_capture.EnvironmentContext) -> CaptureMetadata:
    metadata: CaptureMetadata = {
        "version": SCHEMA_VERSION,
        "source": "atuin",
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if environment:
        metadata["environment"] = environment
    return metadata


def _entry_record(entry: HistoryEntry, git: context_capture.GitContext | None = None) -> RunRecord:
    captured = entry.output is not None
    text = entry.output or ""
    captured_bytes = len(text.encode("utf-8", errors="surrogatepass"))
    truncated = entry.output_truncated if captured else None
    exit_complete = entry.output_exit_capture_complete if captured else None
    if not captured:
        completeness: OutputCompleteness = "unavailable"
    elif truncated is True or exit_complete is False:
        completeness = "incomplete"
    else:
        completeness = "unknown"
    output: OutputRecord = {
        "state": "captured" if captured else "unavailable",
        "error": entry.output_error,
        "source": "atuin-pty-proxy" if captured else "atuin-history-only",
        "text": text,
        "captured_bytes": captured_bytes,
        "presented_bytes": captured_bytes,
        "completeness": completeness,
        "truncated": truncated,
        "observed_bytes": entry.output_observed_bytes if captured else None,
        "total_bytes": entry.output_total_bytes if captured else None,
    }
    if exit_complete is not None:
        output["exit_capture_complete"] = exit_complete
    # PTY traffic includes redraws, so these sizes cannot prove loss. A large
    # discrepancy is nevertheless useful evidence of a possibly incomplete
    # terminal-rendered snapshot (rather than a complete transcript).
    observed = entry.output_observed_bytes if captured else None
    if (
        observed is not None
        and observed - captured_bytes >= 65536
        and observed >= 8 * max(captured_bytes, 1)
    ):
        output["coverage_warning"] = "rendered-snapshot-much-smaller-than-pty-traffic"

    context: ContextRecord = {"cwd": entry.cwd}
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


def _git_context(
    entry: HistoryEntry, options: ContextOptions | None
) -> context_capture.GitContext | None:
    if options is None:
        return None
    return context_capture.capture_git_context(entry.cwd, options)


def capture_context(
    entries: list[HistoryEntry], context_options: ContextOptions | None
) -> ContextSnapshot:
    """Snapshot all subprocess-dependent context before entering gRPC."""
    environment: context_capture.EnvironmentContext = {}
    if context_options is not None:
        environment = context_capture.capture_environment(context_options)
    git_by_cwd: dict[str, context_capture.GitContext | None] = {}
    for entry in entries:
        if entry.cwd not in git_by_cwd:
            git_by_cwd[entry.cwd] = _git_context(entry, context_options)
    return ContextSnapshot(environment=environment, git_by_cwd=git_by_cwd)


def build_record_from_entries(
    entries: list[HistoryEntry],
    *,
    context_options: ContextOptions | None = None,
    snapshot: ContextSnapshot | None = None,
) -> CopoutRecord:
    """Build one schema-v9 capture envelope from chronological entries."""
    if not entries:
        raise ValueError("a Copout record requires at least one run")

    captured = snapshot if snapshot is not None else capture_context(entries, context_options)
    runs = [_entry_record(entry, captured.git_by_cwd.get(entry.cwd)) for entry in entries]
    return {
        **_metadata(captured.environment),
        "runs": runs,
    }


def build_record(*, context_options: ContextOptions | None = None) -> CopoutRecord:
    entries = recent_history(1)
    if not entries:
        raise AtuinError("no previous non-copout command found in the current Atuin session")
    snapshot = capture_context(entries, context_options)
    return build_record_from_entries(hydrate_outputs(entries), snapshot=snapshot)


def build_history(
    *,
    count: int,
    failed_only: bool = False,
    context_options: ContextOptions | None = None,
) -> CopoutRecord:
    entries = recent_history(count, failed_only=failed_only)
    if not entries:
        qualifier = "failed " if failed_only else ""
        raise AtuinError(f"no {qualifier}non-copout commands found in the current Atuin session")
    snapshot = capture_context(entries, context_options)
    hydrated = hydrate_outputs(entries)
    hydrated.reverse()
    return build_record_from_entries(hydrated, snapshot=snapshot)
