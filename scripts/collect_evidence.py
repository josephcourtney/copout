#!/usr/bin/env python3
"""Collect reproducible Atuin/Copout/Kitty output evidence in one directory.

Run after the target command. Optionally copy its visible output in Kitty
before running this script with --kitty-clipboard.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from copout import atuin
from copout.terminal import plain_terminal_text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output directory")
    parser.add_argument("--history-id", help="Use this exact Atuin history ID")
    parser.add_argument(
        "--kitty-clipboard",
        action="store_true",
        help="Save current macOS clipboard as the Kitty-selected reference",
    )
    args = parser.parse_args()

    entries = list(enumerate(atuin.recent_history(100), start=1))
    if args.history_id:
        matches = [
            (position, entry) for position, entry in entries if entry.id == args.history_id
        ]
    else:
        # The collector may appear in preexec history; skip its own entry.
        matches = [
            (position, entry)
            for position, entry in entries
            if "collect_evidence.py" not in entry.command
        ]
    if not matches:
        parser.error("target command not found in the current Atuin session")
    position, selected = matches[0]
    upstream = atuin.hydrate_outputs([selected])[0]
    out = args.output or Path(
        f"copout-evidence-{datetime.now().astimezone():%Y%m%d-%H%M%S}"
    )
    out.mkdir(parents=True, exist_ok=False)
    if upstream.output is not None:
        (out / "atuin-snapshot.txt").write_text(
            upstream.output, encoding="utf-8", errors="surrogatepass"
        )

    def capture_cli(*flags: str) -> str:
        return subprocess.run(
            [sys.executable, "-m", "copout.cli", "--print", *flags, str(position)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    # Collect the actual user-facing CLI paths, not just the shared renderer.
    json_text = capture_cli("--json")
    xml_text = capture_cli()
    md_text = capture_cli("--markdown")
    for filename, contents in (
        ("copout.json", json_text),
        ("copout.xml", xml_text),
        ("copout.md", md_text),
    ):
        (out / filename).write_text(contents, encoding="utf-8")

    capture = json.loads(json_text)["runs"][0]
    if capture["history_id"] != selected.id:
        raise RuntimeError("Atuin history positions shifted while collecting evidence")
    summary = {
        "history_id": selected.id,
        "command": selected.command,
        "cwd": selected.cwd,
        "status": selected.exit_status,
        "duration_seconds": selected.duration,
        "upstream": {
            "available": upstream.output is not None,
            "snapshot_bytes": (
                len(upstream.output.encode("utf-8", errors="surrogatepass"))
                if upstream.output is not None
                else None
            ),
            "truncated": upstream.output_truncated,
            "observed_bytes": upstream.output_observed_bytes,
            "exit_capture_complete": upstream.output_exit_capture_complete,
            "error": upstream.output_error,
        },
        "marker_presence": {
            marker: marker in capture["output"]["text"]
            for marker in (
                "__COPOUT_PROBE_BEGIN__",
                "__COPOUT_PROBE_END__",
                "__COPOUT_STDERR__",
            )
        },
        "output": {
            key: value
            for key, value in capture["output"].items()
            if key != "text"
        },
    }
    if args.kitty_clipboard:
        kitty = subprocess.run(
            ["pbpaste"], check=True, capture_output=True, text=True
        ).stdout
        (out / "kitty-selection.txt").write_text(kitty, encoding="utf-8")
        def save_diff(filename: str, label: str, expected: str) -> None:
            differences = difflib.unified_diff(
                kitty.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile="Kitty visible selection (may include prompts)",
                tofile=label,
            )
            (out / filename).write_text("".join(differences), encoding="utf-8")

        summary["kitty_selection_bytes"] = len(kitty.encode("utf-8"))
        if upstream.output is not None:
            normalized = plain_terminal_text(upstream.output)
            (out / "atuin-normalized.txt").write_text(normalized, encoding="utf-8")
            save_diff("kitty-vs-atuin.diff", "Full normalized Atuin snapshot", normalized)
            summary["kitty_matches_normalized_atuin"] = kitty == normalized
            summary["copout_matches_normalized_atuin"] = (
                capture["output"]["text"] == normalized
            )
        save_diff(
            "kitty-vs-copout.diff",
            "Copout presentation (may be explicitly truncated)",
            capture["output"]["text"],
        )
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{out}: {selected.command!r} [{capture['output']['completeness']}]")


if __name__ == "__main__":
    main()
