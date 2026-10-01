from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .atuin import HistoryEntry

DEFAULT_PICK_LIMIT = 100


class SelectionError(ValueError):
    """Invalid or unavailable command selection."""


def parse_selectors(tokens: Sequence[str], *, available: int) -> list[int]:
    """Return selected zero-based newest-first offsets, sorted oldest-first."""
    if not tokens:
        raise SelectionError("no commands selected")
    if available < 1:
        raise SelectionError("no recent commands are available")

    selected: set[int] = set()
    for token in tokens:
        for raw_part in token.split(","):
            part = raw_part.strip()
            if not part:
                raise SelectionError(f"invalid empty selector in {token!r}")
            if "-" in part:
                bounds = part.split("-", 1)
                if len(bounds) != 2 or not all(bound.isdigit() for bound in bounds):
                    raise SelectionError(f"invalid selector {part!r}")
                start, end = (int(bound) for bound in bounds)
                if start < 1 or end < 1:
                    raise SelectionError("selectors are 1-based and must be positive")
                if end < start:
                    raise SelectionError(f"range {part!r} must run from newer to older")
                values = range(start, end + 1)
            else:
                if not part.isdigit():
                    raise SelectionError(f"invalid selector {part!r}")
                value = int(part)
                if value < 1:
                    raise SelectionError("selectors are 1-based and must be positive")
                values = (value,)

            for value in values:
                if value > available:
                    raise SelectionError(
                        f"selector {value} is outside the {available} available commands"
                    )
                selected.add(value - 1)

    # Candidates are newest-first; larger offsets are older. Emit oldest-first.
    return sorted(selected, reverse=True)


def select_entries(entries: Sequence[HistoryEntry], tokens: Sequence[str]) -> list[HistoryEntry]:
    indices = parse_selectors(tokens, available=len(entries))
    return [entries[index] for index in indices]


def parse_record_ids(tokens: Sequence[str]) -> list[str]:
    """Return unique non-empty record IDs from comma-separated option values."""
    record_ids: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        for raw_id in token.split(","):
            record_id = raw_id.strip()
            if not record_id:
                raise SelectionError(f"invalid empty record ID in {token!r}")
            if record_id not in seen:
                seen.add(record_id)
                record_ids.append(record_id)
    if not record_ids:
        raise SelectionError("no records selected")
    return record_ids


def select_entries_by_ids(
    entries: Sequence[HistoryEntry], record_ids: Sequence[str]
) -> list[HistoryEntry]:
    """Return the requested records chronologically, rejecting unknown IDs."""
    if not record_ids:
        raise SelectionError("no records selected")

    requested = set(record_ids)
    found = {entry.id for entry in entries}
    missing = [record_id for record_id in record_ids if record_id not in found]
    if missing:
        ids = ", ".join(missing)
        raise SelectionError(f"record ID(s) not available: {ids}")

    # Candidates are newest-first; emit selected records oldest-first.
    return [entry for entry in reversed(entries) if entry.id in requested]


def _duration_text(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.1f}s"


def _status_text(status: int | None) -> str:
    if status is None:
        return "?"
    return "✓" if status == 0 else f"✗{status}"


def candidate_lines(entries: Sequence[HistoryEntry]) -> list[str]:
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        command = " ".join(entry.command.splitlines())
        if len(command) > 100:
            command = command[:97] + "..."
        lines.append(
            f"{index:>3}  {_status_text(entry.exit_status):>3}  "
            f"{_duration_text(entry.duration):>7}  {command}"
        )
    return lines
