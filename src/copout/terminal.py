"""Normalize retained terminal snapshots into safe, readable text.

Atuin supplies a terminal rendering, not a complete PTY transcript. Cursor
controls are interpreted where practical; missing scrollback cannot be restored.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_ESCAPES = re.compile(
    r"\x1b\[([0-?]*[ -/]*)([@-~])"
    r"|\x1b\][^\x1b\x07]*(?:\x07|\x1b\\)"
    r"|\x1b[P^_X].*?\x1b\\"
    r"|\x1b[78=>]",
    re.DOTALL,
)


def _csi_arg(parts: Sequence[str], position: int = 0, default: int = 1) -> int:
    """Read a bounded CSI numeric argument without closing over loop state."""
    if position >= len(parts) or not parts[position].isdigit():
        return default
    return min(int(parts[position]), 4096)


def plain_terminal_text(text: str) -> str:
    """Apply common VT cursor controls and remove terminal escape sequences."""
    rows: list[list[str]] = [[]]
    row = column = index = 0

    def ensure_row() -> None:
        while len(rows) <= row:
            rows.append([])

    def write(characters: str) -> None:
        nonlocal column
        for character in characters:
            line = rows[row]
            if column >= len(line):
                line.extend(" " * (column - len(line)))
                line.append(character)
            else:
                line[column] = character
            column += 1

    while index < len(text):
        match = _ESCAPES.match(text, index)
        if match is not None:
            params, action = match.group(1), match.group(2)
            if action is not None:
                parts = (params or "").split(";")

                amount = _csi_arg(parts)
                if action == "K":
                    mode = _csi_arg(parts, default=0)
                    if mode == 0:
                        del rows[row][column:]
                    elif mode == 1:
                        line = rows[row]
                        width = min(column + 1, len(line))
                        line[:width] = [" "] * width
                    elif mode == 2:
                        rows[row] = []
                elif action == "A":
                    row = max(0, row - amount)
                elif action == "B":
                    row += amount
                    ensure_row()
                elif action == "C":
                    column = min(column + amount, 100_000)
                elif action == "D":
                    column = max(0, column - amount)
                elif action == "G":
                    column = amount - 1
                elif action in ("H", "f"):
                    row = max(0, _csi_arg(parts) - 1)
                    column = max(0, _csi_arg(parts, 1) - 1)
                    ensure_row()
                elif action == "J" and _csi_arg(parts, default=0) == 2:
                    rows = [[]]
                    row = column = 0
            index = match.end()
            continue

        character = text[index]
        index += 1
        if character == "\n":
            row += 1
            column = 0
            ensure_row()
        elif character == "\r":
            column = 0
        elif character == "\b":
            column = max(0, column - 1)
        elif character == "\t":
            write(" " * (8 - column % 8))
        elif character == "\x1b":
            write("\\x1b")
        else:
            value = ord(character)
            if (
                value < 32
                or 0x7F <= value < 0xA0
                or 0xD800 <= value <= 0xDFFF
                or (value & 0xFFFF in (0xFFFE, 0xFFFF))
            ):
                write(ascii(character)[1:-1])
            else:
                write(character)

    return "\n".join("".join(line) for line in rows).rstrip(" \t\r\n")
