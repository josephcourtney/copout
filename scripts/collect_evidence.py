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
from datetime import datetime
from pathlib import Path

from copout import atuin, record, render


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

    entries = atuin.recent_history(100)
    if args.history_id:
        matches = [entry for entry in entries if entry.id == args.history_id]
    else:
        # The collector may already appear in preexec history; ignore itself.
        matches = [
            entry for entry in entries if "collect_evidence.py" not in entry.command
        ]
    if not matches:
        parser.error("target command not found in the current Atuin session")
    selected = atuin.hydrate_outputs([matches[0]])[0]
    evidence = record.build_record_from_entries([selected])
    out = args.output or Path(
        f"copout-evidence-{datetime.now().astimezone():%Y%m%d-%H%M%S}"
    )
    out.mkdir(parents=True, exist_ok=False)

    json_text = render.render(evidence, as_json=True)
    xml_text = render.render(evidence)
    md_text = render.render(evidence, as_markdown=True)
    for filename, contents in (
        ("copout.json", json_text),
        ("copout.xml", xml_text),
        ("copout.md", md_text),
    ):
        (out / filename).write_text(contents, encoding="utf-8")

    capture = json.loads(json_text)["runs"][0]
    summary = {
        "history_id": selected.id,
        "command": selected.command,
        "cwd": selected.cwd,
        "status": selected.exit_status,
        "duration_seconds": selected.duration,
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
        differences = difflib.unified_diff(
            kitty.splitlines(keepends=True),
            capture["output"]["text"].splitlines(keepends=True),
            fromfile="Kitty visible selection (may contain prompt)",
            tofile="Atuin rendered snapshot (Copout plain text)",
        )
        (out / "kitty-vs-copout.diff").write_text(
            "".join(differences), encoding="utf-8"
        )
        summary["kitty_selection_bytes"] = len(kitty.encode("utf-8"))
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{out}: {selected.command!r} [{capture['output']['completeness']}]")


if __name__ == "__main__":
    main()
