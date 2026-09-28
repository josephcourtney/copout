from __future__ import annotations

import pytest

from copout import selection
from copout.atuin import HistoryEntry


def test_parse_selectors_deduplicates_and_returns_chronological_offsets() -> None:
    assert selection.parse_selectors(["1", "3", "5-6", "3"], available=8) == [5, 4, 2, 0]


@pytest.mark.parametrize("tokens", [["0"], ["-1"], ["3-2"], ["x"], ["1-x"], ["1,,2"]])
def test_parse_selectors_rejects_invalid_input(tokens: list[str]) -> None:
    with pytest.raises(selection.SelectionError):
        selection.parse_selectors(tokens, available=8)


def test_parse_selectors_rejects_out_of_window_offset() -> None:
    with pytest.raises(selection.SelectionError, match="outside"):
        selection.parse_selectors(["4"], available=3)


def test_select_entries_returns_oldest_first() -> None:
    entries = [
        HistoryEntry("3", "newest"),
        HistoryEntry("2", "middle"),
        HistoryEntry("1", "oldest"),
    ]
    assert [entry.command for entry in selection.select_entries(entries, ["1", "3"])] == [
        "oldest",
        "newest",
    ]


def test_candidate_lines_are_compact() -> None:
    entries = [
        HistoryEntry("2", "echo one\necho two", exit_status=0, duration=0.012),
        HistoryEntry("1", "false", exit_status=1, duration=1.2),
    ]
    lines = selection.candidate_lines(entries)
    assert "echo one echo two" in lines[0]
    assert "✓" in lines[0]
    assert "12ms" in lines[0]
    assert "✗1" in lines[1]
