from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import ClassVar, TextIO

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import SelectionList, Static

from .atuin import HistoryEntry
from .selection import SelectionError, candidate_lines


class CommandPicker(App[list[int] | None]):
    """Inline checklist for selecting recent commands."""

    INLINE_PADDING = 0
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen {
        &:inline {
            border: none;
            height: 60vh;
            min-height: 8;
            max-height: 16;
        }
    }

    #commands {
        width: 100%;
        height: 1fr;
        border: round $accent;
        padding: 0 1;
        scrollbar-size: 1 1;
    }

    #picker-help {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "confirm", "Copy", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("q", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", show=False, priority=True),
    ]

    def __init__(self, entries: Sequence[HistoryEntry]) -> None:
        super().__init__()
        self._entries = list(entries)

    def compose(self) -> ComposeResult:
        options = [(line, index) for index, line in enumerate(candidate_lines(self._entries))]
        yield SelectionList[int](*options, id="commands", compact=True)
        yield Static(self._help_text(0), id="picker-help")

    def on_mount(self) -> None:
        choices = self.query_one("#commands", SelectionList)
        choices.border_title = f"Recent commands — {len(self._entries)} available"
        choices.highlighted = 0
        choices.focus()

    @on(SelectionList.SelectedChanged)
    def update_selection_count(self) -> None:
        selected = self.query_one("#commands", SelectionList).selected
        self.query_one("#picker-help", Static).update(self._help_text(len(selected)))

    @staticmethod
    def _help_text(selected: int) -> str:
        return (
            f"{selected} selected  ↑↓ navigate  Space toggle  "
            "Enter copy  Esc/q cancel"
        )

    def action_confirm(self) -> None:
        choices = self.query_one("#commands", SelectionList)
        selected = [int(value) for value in choices.selected]
        if not selected:
            self.query_one("#picker-help", Static).update(
                "Select at least one command  ↑↓ navigate  Space toggle  Esc/q cancel"
            )
            self.bell()
            return

        # Candidates are newest-first; larger indexes are older. Emit oldest-first.
        self.exit(sorted(selected, reverse=True))

    def action_cancel(self) -> None:
        self.exit(None)


@contextmanager
def _terminal_streams() -> Iterator[tuple[TextIO, TextIO]]:
    """Route the inline UI to the controlling terminal, never structured stdout."""
    if sys.stdin.isatty() and sys.stderr.isatty():
        yield sys.stdin, sys.stderr
        return

    try:
        with open("/dev/tty", "r+", encoding="utf-8", buffering=1) as tty:
            yield tty, tty
    except OSError as exc:
        raise SelectionError(
            "interactive selection requires a controlling terminal; pass selectors explicitly"
        ) from exc


def pick_entries(entries: Sequence[HistoryEntry]) -> list[HistoryEntry] | None:
    """Run the inline picker and return selected entries chronologically, or None on cancel."""
    if not entries:
        raise SelectionError("no recent commands are available")

    with _terminal_streams() as (input_stream, output_stream):
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        try:
            # Textual binds to standard streams when the app starts. Point it at the
            # controlling terminal so `copout pick -p > context.xml` stays clean.
            sys.stdin = input_stream
            sys.stdout = output_stream
            indexes = CommandPicker(entries).run(
                inline=True,
                inline_no_clear=False,
                mouse=False,
            )
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout

    if indexes is None:
        return None
    return [entries[index] for index in indexes]
