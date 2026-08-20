from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from typing import Protocol

from jerakeen import connect

_HISTORY_FIELD_SEPARATOR = "\x1f"
_HISTORY_FORMAT = _HISTORY_FIELD_SEPARATOR.join(
    ("{uuid}", "{time}", "{directory}", "{exit}", "{duration}", "{command}")
)
_DURATION_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(ns|µs|us|ms|s|m|h)")


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


class CommandOutputLike(Protocol):
    @property
    def text(self) -> str: ...


class SemanticLike(Protocol):
    async def output(self, history_id: str) -> CommandOutputLike | None: ...


class DaemonStatusLike(Protocol):
    @property
    def healthy(self) -> bool: ...

    @property
    def version(self) -> str: ...

    @property
    def pid(self) -> int: ...

    @property
    def protocol(self) -> int: ...


class JerakeenClientLike(Protocol):
    @property
    def description(self) -> str: ...

    @property
    def semantic(self) -> SemanticLike: ...

    async def status(self) -> DaemonStatusLike: ...


type JerakeenContextLike = AbstractAsyncContextManager[JerakeenClientLike]

ConnectFactory = Callable[..., JerakeenContextLike]
HistoryLoader = Callable[[], list[HistoryEntry]]


def _duration_seconds(text: str | None) -> float | None:
    if text is None:
        return None
    match = _DURATION_RE.fullmatch(text.strip())
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
        try:
            exit_status = int(exit_text)
        except ValueError:
            exit_status = None
        if not history_id or not command:
            continue
        entries.append(
            HistoryEntry(
                id=history_id,
                command=command,
                cwd=cwd,
                exit_status=exit_status,
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

    args = [
        atuin_path,
        "history",
        "list",
        "--session",
        "--print0",
        "--reverse=false",
        "--format",
        _HISTORY_FORMAT,
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AtuinError(f"failed to read Atuin history: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise AtuinError(f"`atuin history list` failed with status {result.returncode}{suffix}")
    return _parse_history_list(result.stdout)


def _connect_jerakeen(*, timeout: float = 3.0) -> JerakeenContextLike:
    return connect(timeout=timeout)


def _is_copout_command(command: str) -> bool:
    words = re.split(r"\s+", command.strip())
    if not words:
        return False
    executable = words[0].rsplit("/", 1)[-1]
    return executable == "copout"


async def _add_outputs(
    entries: list[HistoryEntry],
    *,
    connect_factory: ConnectFactory,
) -> list[HistoryEntry]:
    try:
        async with connect_factory(timeout=3.0) as atuin:
            populated: list[HistoryEntry] = []
            for entry in entries:
                try:
                    output = await atuin.semantic.output(entry.id)
                except Exception:  # output is best-effort and intentionally ephemeral
                    output = None
                populated.append(replace(entry, output=None if output is None else output.text))
            return populated
    except Exception:
        # Persistent history remains useful when the daemon or its ephemeral
        # command-output cache is unavailable.
        return entries


def recent_entries(
    count: int,
    *,
    failed_only: bool = False,
    include_output: bool = True,
    history_loader: HistoryLoader = _load_history,
    connect_factory: ConnectFactory = _connect_jerakeen,
) -> list[HistoryEntry]:
    requested = max(count, 1)
    entries = [entry for entry in history_loader() if not _is_copout_command(entry.command)]
    if failed_only:
        entries = [
            entry for entry in entries if entry.exit_status is not None and entry.exit_status != 0
        ]
    # `_load_history` requests Atuin's native newest-first ordering. Preserve it
    # so sub-second ordering does not depend on the rendered timestamp format.
    entries = entries[:requested]
    if not include_output or not entries:
        return entries
    return asyncio.run(_add_outputs(entries, connect_factory=connect_factory))


def previous_entry(
    *,
    history_loader: HistoryLoader = _load_history,
    connect_factory: ConnectFactory = _connect_jerakeen,
) -> HistoryEntry:
    entries = recent_entries(
        1,
        history_loader=history_loader,
        connect_factory=connect_factory,
    )
    if entries:
        return entries[0]
    raise AtuinError("no previous non-copout command found in the current Atuin session")


async def _daemon_info(connect_factory: ConnectFactory) -> DaemonInfo:
    try:
        async with connect_factory(timeout=3.0) as atuin:
            status = await atuin.status()
            return DaemonInfo(
                description=atuin.description,
                healthy=status.healthy,
                version=status.version,
                pid=status.pid,
                protocol=status.protocol,
            )
    except AtuinError:
        raise
    except Exception as exc:
        raise AtuinError(f"Jerakeen could not connect to the Atuin daemon: {exc}") from exc


def daemon_info(*, connect_factory: ConnectFactory = _connect_jerakeen) -> DaemonInfo:
    return asyncio.run(_daemon_info(connect_factory))


__all__ = [
    "AtuinError",
    "DaemonInfo",
    "HistoryEntry",
    "daemon_info",
    "previous_entry",
    "recent_entries",
]
