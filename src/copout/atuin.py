from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass, replace

from jerakeen import connect

from ._process import run_process

_HISTORY_FIELD_SEPARATOR = "\x1f"
_HISTORY_FORMAT = _HISTORY_FIELD_SEPARATOR.join(
    ("{uuid}", "{time}", "{directory}", "{exit}", "{duration}", "{command}")
)
_DURATION_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(ns|µs|us|ms|s|m|h)")
_DURATION_SCALE = {
    "ns": 1e-9,
    "µs": 1e-6,
    "us": 1e-6,
    "ms": 1e-3,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}


class AtuinError(RuntimeError):
    """Failure while retrieving Atuin history or daemon data."""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: str
    command: str
    cwd: str = ""
    exit_status: int | None = None
    duration: float | None = None
    timestamp: str = ""
    output: str | None = None


@dataclass(frozen=True, slots=True)
class DaemonInfo:
    description: str
    healthy: bool
    version: str
    pid: int
    protocol: int


def _duration_seconds(text: str | None) -> float | None:
    if not text or not (match := _DURATION_RE.fullmatch(text.strip())):
        return None

    amount, unit = match.groups()
    return float(amount) * _DURATION_SCALE[unit]


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_history_list(text: str) -> list[HistoryEntry]:
    entries: list[HistoryEntry] = []
    for raw_record in text.split("\0"):
        if not raw_record:
            continue

        fields = raw_record.split(_HISTORY_FIELD_SEPARATOR, 5)
        if len(fields) != 6:
            msg = "Atuin returned `history list` data in an unrecognized format"
            raise AtuinError(msg)

        history_id, timestamp, cwd, exit_text, duration_text, command = fields
        if not history_id or not command:
            continue

        entries.append(
            HistoryEntry(
                id=history_id,
                command=command,
                cwd=cwd,
                exit_status=_int_or_none(exit_text),
                duration=_duration_seconds(duration_text),
                timestamp=timestamp,
            )
        )
    return entries


def _load_history() -> list[HistoryEntry]:
    atuin_path = shutil.which("atuin")
    if atuin_path is None:
        raise AtuinError("Atuin is required but `atuin` is not on PATH")
    if not os.environ.get("ATUIN_SESSION"):
        raise AtuinError("ATUIN_SESSION is not set in this shell")

    result = run_process(
        [
            atuin_path,
            "history",
            "list",
            "--session",
            "--print0",
            "--reverse=false",
            "--format",
            _HISTORY_FORMAT,
        ],
        timeout=5,
    )
    if result.error is not None:
        raise AtuinError(f"failed to read Atuin history: {result.error}")
    if result.returncode != 0:
        detail = result.stderr or result.stdout
        suffix = f": {detail}" if detail else ""
        raise AtuinError(f"`atuin history list` failed with status {result.returncode}{suffix}")
    return _parse_history_list(result.stdout)


def _is_copout_command(command: str) -> bool:
    words = command.split(maxsplit=1)
    return bool(words) and words[0].rsplit("/", 1)[-1] == "copout"


async def _add_outputs(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    async with connect(timeout=3.0) as atuin:

        async def populate(entry: HistoryEntry) -> HistoryEntry:
            try:
                output = await atuin.semantic.output(entry.id)
            except Exception:  # output is best-effort and intentionally ephemeral
                return entry
            return replace(entry, output=None if output is None else output.text)

        return list(await asyncio.gather(*(populate(entry) for entry in entries)))


def recent_entries(
    count: int,
    *,
    failed_only: bool = False,
    include_output: bool = True,
) -> list[HistoryEntry]:
    def selected(entry: HistoryEntry) -> bool:
        if _is_copout_command(entry.command):
            return False
        return not failed_only or (entry.exit_status is not None and entry.exit_status != 0)

    requested = max(count, 1)
    entries = [entry for entry in _load_history() if selected(entry)][:requested]

    # `_load_history` requests Atuin's native newest-first ordering. Preserve it
    # so sub-second ordering does not depend on the rendered timestamp format.
    if not include_output or not entries:
        return entries

    try:
        return asyncio.run(_add_outputs(entries))
    except Exception:
        # Persistent history remains useful when the daemon or its ephemeral
        # command-output cache is unavailable.
        return entries


async def _daemon_info() -> DaemonInfo:
    try:
        async with connect(timeout=3.0) as atuin:
            status = await atuin.status()
            return DaemonInfo(
                description=atuin.description,
                healthy=status.healthy,
                version=status.version,
                pid=status.pid,
                protocol=status.protocol,
            )
    except Exception as exc:
        raise AtuinError(f"Jerakeen could not connect to the Atuin daemon: {exc}") from exc


def daemon_info() -> DaemonInfo:
    return asyncio.run(_daemon_info())
