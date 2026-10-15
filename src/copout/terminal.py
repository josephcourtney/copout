"""Plain-text rendering for Atuin terminal snapshots."""

from __future__ import annotations

import re

# Strip ANSI CSI, OSC, DCS, and the remaining common ESC sequences.
_CONTROL_SEQUENCE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x1b\][^\x1b\x07]*(?:\x07|\x1b\\)"
    r"|\x1b[P^_X].*?\x1b\\"
    r"|\x1b[78=>]",
    re.DOTALL,
)


def plain_terminal_text(text: str) -> str:
    """Produce shareable text, interpreting carriage-return redraws.

    Atuin's snapshot is not a transcript. Earlier screen content absent from
    that snapshot cannot be recovered here.
    """
    text = _CONTROL_SEQUENCE.sub("", text)
    lines: list[str] = []
    for source_line in text.split("\n"):
        cells: list[str] = []
        column = 0
        for char in source_line:
            if char == "\r":
                column = 0
            elif char == "\b":
                column = max(column - 1, 0)
            else:
                if char == "\t":
                    char = " " * (8 - column % 8)
                else:
                    codepoint = ord(char)
                    if codepoint < 32 or 0x7F <= codepoint < 0xA0 or (
                        0xD800 <= codepoint <= 0xDFFF
                    ) or (codepoint & 0xFFFF in (0xFFFE, 0xFFFF)):
                        char = ascii(char)[1:-1]
                for value in char:
                    if column == len(cells):
                        cells.append(value)
                    else:
                        cells[column] = value
                    column += 1
        lines.append("".join(cells))
    return "\n".join(lines).rstrip(" \t\r\n")
