#!/usr/bin/env python3
"""Optional real-Kitty light/dark inline-picker qualification.

Run inside a Kitty instance with remote control enabled:
    uv run python scripts/qualify_picker_themes.py --out /tmp/copout-themes

Launches isolated windows with per-window palettes, verifies OSC 11 theme
selection and saves PNG screenshots. Does not change the calling window.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from copout.atuin import HistoryEntry
from copout.picker import CommandPicker
from copout.picker_theme import detect_theme

PALETTES = {
    "dark": ("#101820", "#f2f4f8", "ansi-dark"),
    "light": ("#f7f5ef", "#252525", "ansi-light"),
}


def kitty_command() -> list[str]:
    if kitten := shutil.which("kitten"):
        return [kitten, "@"]
    if kitty := shutil.which("kitty"):
        return [kitty, "+kitten", "@"]
    raise RuntimeError("Kitty remote control executable not found")


def remote(*args: str) -> str:
    result = subprocess.run(
        [*kitty_command(), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def parse_kitty_colors(report: str) -> dict[str, str]:
    """Parse kitty.conf-style key/value lines independent of whitespace."""
    colors: dict[str, str] = {}
    for line in report.splitlines():
        fields = line.strip().split()
        if len(fields) >= 2 and not fields[0].startswith("#"):
            colors[fields[0]] = fields[1].lower()
    return colors


def child(label: str, marker: Path) -> None:
    class ProbePicker(CommandPicker):
        def on_mount(self) -> None:
            super().on_mount()
            marker.write_text(
                json.dumps({"palette": label, "theme": self.theme}),
                encoding="utf-8",
            )

    chosen = detect_theme(sys.stdin.buffer, sys.stdout.buffer)
    app = ProbePicker(
        [HistoryEntry("2", "recent example"), HistoryEntry("1", "older example")],
        preselected_ids=["1"],
        theme_name=chosen,
    )
    app.run(inline=True, inline_no_clear=False, mouse=False)


def qualify(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, str]] = []
    for label, (background, foreground, expected) in PALETTES.items():
        marker = out / f"{label}.json"
        marker.unlink(missing_ok=True)
        window_id = remote(
            "launch", "--type=os-window",
            "--title", f"copout-picker-theme-{label}",
            "--color", f"background={background}",
            "--color", f"foreground={foreground}",
            sys.executable, str(Path(__file__).resolve()), "--child", label, str(marker),
        ).strip()
        if not window_id.isdigit():
            raise RuntimeError(f"Kitty returned invalid window ID: {window_id!r}")
        try:
            deadline = time.monotonic() + 8
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not marker.exists():
                raise RuntimeError(f"{label}: picker failed to mount")
            state = json.loads(marker.read_text(encoding="utf-8"))
            if state["theme"] != expected:
                raise AssertionError(f"{label}: expected {expected}, got {state['theme']}")
            colors = remote("get-colors", "--match", f"id:{window_id}")
            (out / f"{label}-colors.txt").write_text(colors + "\n", encoding="utf-8")
            actual = parse_kitty_colors(colors)
            time.sleep(0.4)  # allow the first full render to reach Kitty
            shot = out / f"{label}.png"
            remote("screenshot", "--match", f"id:{window_id}", str(shot))
            if not shot.is_file() or shot.stat().st_size == 0:
                raise AssertionError(f"{label}: no PNG screenshot saved")
            if actual.get("background") != background.lower():
                raise AssertionError(
                    f"{label}: expected background {background}, got {actual.get('background')!r}. "
                    f"Full report saved in {out / (label + '-colors.txt')}"
                )
            results.append({"palette": label, "theme": state["theme"], "screenshot": str(shot)})
        finally:
            remote("close-window", "--match", f"id:{window_id}")
    (out / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(out / "summary.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Screenshot and metadata directory")
    parser.add_argument("--child", nargs=2, metavar=("PALETTE", "MARKER"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        child(args.child[0], Path(args.child[1]))
    elif args.out:
        qualify(args.out)
    else:
        parser.error("--out is required")


if __name__ == "__main__":
    main()
