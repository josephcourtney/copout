"""Bounded terminal-background query for the inline picker.

The terminal, not macOS appearance, determines the light/dark ANSI theme.
Only query an interactive TTY; never write escape codes to structured stdout.
"""

from __future__ import annotations

import os
import re
import select
import termios
import time
import tty
from typing import BinaryIO

_QUERY = b"\x1b]11;?\x1b\\"
_RESPONSE = re.compile(rb"\x1b\]11;rgb:([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})(?:\x07|\x1b\\)")
_MAX_RESPONSE = 128
_TIMEOUT = 0.15


def parse_background_response(response: bytes) -> tuple[float, float, float] | None:
    """Parse OSC 11 RGB components, scaled from 4–16 bits to the unit interval."""
    match = _RESPONSE.search(response)
    if match is None:
        return None
    parts = match.groups()
    return (
        int(parts[0], 16) / (16 ** len(parts[0]) - 1),
        int(parts[1], 16) / (16 ** len(parts[1]) - 1),
        int(parts[2], 16) / (16 ** len(parts[2]) - 1),
    )


def theme_for_background(rgb: tuple[float, float, float] | None) -> str:
    """Return an ANSI theme using the WCAG luminance midpoint for black/white text."""
    if rgb is None:
        return "ansi-dark"

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(component) for component in rgb)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "ansi-light" if luminance > 0.179 else "ansi-dark"


def query_background(
    input_stream: BinaryIO,
    output_stream: BinaryIO | None = None,
    *,
    timeout: float = _TIMEOUT,
) -> tuple[float, float, float] | None:
    """Ask OSC 11 on a TTY with bounded input and restore its attributes.

    This must run before Textual starts reading input. No subprocess or Kitty
    remote-control connection is needed.
    """
    try:
        fd = input_stream.fileno()
        output_fd = (output_stream if output_stream is not None else input_stream).fileno()
        if not os.isatty(fd) or not os.isatty(output_fd):
            return None
        original = termios.tcgetattr(fd)
    except (OSError, ValueError, termios.error):
        return None

    response = bytearray()
    try:
        tty.setcbreak(fd)
        os.write(output_fd, _QUERY)
        deadline = time.monotonic() + max(0.0, timeout)
        while len(response) < _MAX_RESPONSE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                break
            chunk = os.read(fd, 1)
            if not chunk:
                break
            response.extend(chunk)
            if chunk == b"\x07" or response.endswith(b"\x1b\\"):
                parsed = parse_background_response(bytes(response))
                if parsed is not None:
                    return parsed
        return None
    except (OSError, ValueError, termios.error):
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def detect_theme(input_stream: BinaryIO, output_stream: BinaryIO | None = None) -> str:
    """Choose a terminal-native ANSI theme, defaulting safely to dark."""
    return theme_for_background(query_background(input_stream, output_stream))
