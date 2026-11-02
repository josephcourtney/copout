from __future__ import annotations

import os
import pty
import threading

import pytest

from copout import picker_theme


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (b"\x1b]11;rgb:0000/0000/0000\x1b\\", (0.0, 0.0, 0.0)),
        (b"\x1b]11;rgb:ffff/ffff/ffff\x07", (1.0, 1.0, 1.0)),
        (b"\x1b]11;rgb:80/40/20\x07", (128 / 255, 64 / 255, 32 / 255)),
        (b"junk", None),
        (b"\x1b]10;rgb:ffff/ffff/ffff\x07", None),
        (b"\x1b]11;rgb:gg/00/00\x07", None),
    ],
)
def test_osc_background_parser(response, expected) -> None:
    assert picker_theme.parse_background_response(response) == expected


@pytest.mark.parametrize(
    ("rgb", "theme"),
    [
        ((0.0, 0.0, 0.0), "ansi-dark"),
        ((0.1, 0.1, 0.15), "ansi-dark"),
        ((1.0, 1.0, 1.0), "ansi-light"),
        ((0.93, 0.92, 0.85), "ansi-light"),
        (None, "ansi-dark"),
    ],
)
def test_theme_classification(rgb, theme) -> None:
    assert picker_theme.theme_for_background(rgb) == theme


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (b"\x1b]11;rgb:ffff/ffff/ffff\x07", "ansi-light"),
        (b"\x1b]11;rgb:0000/0000/0000\x1b\\", "ansi-dark"),
        (None, "ansi-dark"),
    ],
)
def test_pty_query_restores_terminal(response, expected) -> None:
    """Exercise a real POSIX PTY, including timeout and echo restoration."""
    import termios

    master, slave = pty.openpty()
    with os.fdopen(slave, "rb", buffering=0) as stream:
        before = termios.tcgetattr(slave)

        def responder() -> None:
            query = bytearray()
            while not query.endswith(b"\x1b\\"):
                query.extend(os.read(master, 1))
            if response is not None:
                os.write(master, response)

        thread = threading.Thread(target=responder, daemon=True)
        thread.start()
        try:
            result = picker_theme.theme_for_background(
                picker_theme.query_background(stream, timeout=0.04 if response is None else 0.3)
            )
            assert result == expected
            assert termios.tcgetattr(slave) == before
            thread.join(timeout=1)
            assert not thread.is_alive()
        finally:
            os.close(master)


def test_non_tty_does_not_send_probe() -> None:
    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            assert picker_theme.query_background(stream) is None
        os.set_blocking(write_fd, False)
        # No OSC request is written to unrelated descriptors.
        assert picker_theme.theme_for_background(None) == "ansi-dark"
    finally:
        os.close(write_fd)
