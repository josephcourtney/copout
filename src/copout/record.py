from __future__ import annotations

from datetime import datetime
from typing import Any

from .atuin import AtuinError, HistoryEntry, previous_entry, recent_entries

SCHEMA_VERSION = 2


def _entry_record(entry: HistoryEntry) -> dict[str, Any]:
    output = entry.output
    return {
        "history_id": entry.id,
        "command": entry.command,
        "result": {"status": entry.exit_status},
        "output": {
            "state": "captured" if output is not None else "unavailable",
            "source": "atuin-pty-proxy" if output is not None else "atuin-history-only",
            "text": output or "",
            "utf8_bytes": len((output or "").encode("utf-8")),
        },
        "context": {"cwd": entry.cwd},
        "timing": {"duration": entry.duration, "recorded_at": entry.timestamp},
    }


def build_record(*, verbose: bool = False) -> dict[str, Any]:
    del verbose
    entry = previous_entry()
    record = _entry_record(entry)
    record.update(
        {
            "version": SCHEMA_VERSION,
            "scope": "command",
            "capture": {
                "association": "atuin-history",
                "reason": "ok",
                "history_source": "atuin",
                "output_source": record["output"]["source"],
            },
            "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
    return record


def build_history(
    *, count: int, failed_only: bool = False, verbose: bool = False
) -> dict[str, Any]:
    del verbose
    entries = recent_entries(count, failed_only=failed_only)
    entries.reverse()
    runs = [_entry_record(entry) for entry in entries]
    return {
        "version": SCHEMA_VERSION,
        "scope": "history",
        "runs": runs,
        "history": {
            "selected": len(runs),
            "requested": count,
            "failed_only": failed_only,
            "source": "atuin",
            "outputs_available": sum(run["output"]["state"] == "captured" for run in runs),
        },
        "capture": {
            "association": "atuin-history",
            "reason": "ok",
            "history_source": "atuin",
            "output_source": "atuin-pty-proxy",
        },
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


__all__ = ["AtuinError", "build_history", "build_record"]
