from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
from collections.abc import Collection
from dataclasses import dataclass, replace

from jerakeen import AtuinUnsupportedError, connect

from ._process import run_process

_DAEMON_TIMEOUT = 3.0
_OUTPUT_CONCURRENCY = 16

_HISTORY_FIELD_SEPARATOR = "\x1f"
_HISTORY_FORMAT = _HISTORY_FIELD_SEPARATOR.join(
    ("{uuid}", "{time}", "{directory}", "{exit}", "{duration}", "{command}")
)
_DURATION_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(ns|µs|us|ms|s|m|h)")
_PYTHON_COMMAND_RE = re.compile(r"python(?:\d+(?:\.\d+)*)?")
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
    output_truncated: bool | None = None
    output_observed_bytes: int | None = None
    output_total_bytes: int | None = None
    output_error: str | None = None
    output_exit_capture_complete: bool | None = None


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


def _command_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def _is_python_command(word: str) -> bool:
    return _PYTHON_COMMAND_RE.fullmatch(_command_name(word)) is not None


def _is_copout_command(command: str) -> bool:
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    if not words:
        return False

    if _command_name(words[0]) == "command":
        words = words[1:]
    if not words:
        return False

    launcher = _command_name(words[0])
    if launcher == "uv" and words[1:2] == ["run"]:
        words = words[2:]
        if words[:1] == ["--"]:
            words = words[1:]
    elif launcher == "uvx":
        words = words[1:]
        if words[:1] == ["--"]:
            words = words[1:]

    if not words:
        return False
    if _command_name(words[0]) == "copout":
        return True
    return _is_python_command(words[0]) and words[1:3] == ["-m", "copout.cli"]


def _output_error(exc: Exception) -> str:
    # Keep upstream diagnostics useful without copying unbounded text into the record.
    detail = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {detail[:500]}"


async def _add_outputs(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    async with connect(timeout=_DAEMON_TIMEOUT, rpc_timeout=_DAEMON_TIMEOUT) as atuin:
        semaphore = asyncio.Semaphore(_OUTPUT_CONCURRENCY)

        async def populate(entry: HistoryEntry) -> HistoryEntry:
            async with semaphore:
                try:
                    async with asyncio.timeout(_DAEMON_TIMEOUT):
                        output = await atuin.history.output(entry.id)
                except AtuinUnsupportedError as exc:
                    detail = " ".join(str(exc).split())[:500]
                    error = "Atuin daemon does not implement command-output retrieval"
                    if detail:
                        error = f"{error} ({detail})"
                    return replace(entry, output_error=error)
                except TimeoutError:
                    return replace(entry, output_error="Atuin daemon output request timed out")
                except Exception as exc:  # preserve history, but report why output is unavailable
                    return replace(entry, output_error=_output_error(exc))

                if output is None:
                    return replace(
                        entry,
                        output_error="Atuin daemon returned no captured output for this history entry",
                    )

                return replace(
                    entry,
                    output=output.text,
                    output_truncated=output.truncated,
                    output_observed_bytes=output.observed_bytes,
                )

        return list(await asyncio.gather(*(populate(entry) for entry in entries)))


def recent_history(
    count: int,
    *,
    failed_only: bool = False,
    required_ids: Collection[str] = (),
) -> list[HistoryEntry]:
    """Return recent matching history newest-first without contacting the daemon.

    required_ids extends the normal candidate window contiguously through the
    oldest required record. This preserves true relative history positions in
    interactive displays while still rejecting unknown IDs in the selection layer.
    """

    def selected(entry: HistoryEntry) -> bool:
        if _is_copout_command(entry.command):
            return False
        return not failed_only or (entry.exit_status is not None and entry.exit_status != 0)

    requested = max(count, 1)
    required = set(required_ids)
    entries = [entry for entry in _load_history() if selected(entry)]
    if required:
        required_positions = [
            index for index, entry in enumerate(entries, start=1) if entry.id in required
        ]
        if required_positions:
            requested = max(requested, *required_positions)
    return entries[:requested]


def hydrate_outputs(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """Fetch captured output only for the supplied history entries."""
    if not entries:
        return []
    try:
        return asyncio.run(_add_outputs(entries))
    except Exception as exc:
        # Persistent history remains useful when the daemon is unavailable.
        return [replace(entry, output_error=_output_error(exc)) for entry in entries]


def recent_entries(
    count: int,
    *,
    failed_only: bool = False,
    include_output: bool = True,
) -> list[HistoryEntry]:
    entries = recent_history(count, failed_only=failed_only)
    return hydrate_outputs(entries) if include_output else entries


async def _daemon_info() -> DaemonInfo:
    try:
        async with connect(timeout=_DAEMON_TIMEOUT, rpc_timeout=_DAEMON_TIMEOUT) as atuin:
            async with asyncio.timeout(_DAEMON_TIMEOUT):
                status = await atuin.status()
            return DaemonInfo(
                description=atuin.description,
                healthy=status.healthy,
                version=status.version,
                pid=status.pid,
                protocol=status.protocol,
            )
    except TimeoutError as exc:
        raise AtuinError("Atuin daemon status request timed out") from exc
    except Exception as exc:
        raise AtuinError(f"Jerakeen could not connect to the Atuin daemon: {exc}") from exc


def daemon_info() -> DaemonInfo:
    return asyncio.run(_daemon_info())
