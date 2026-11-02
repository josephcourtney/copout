#!/usr/bin/env python3
"""Inspect an already-captured Copout JSON record for exact output-probe fidelity.

Run the probe as its own command in a Kitty shell with Atuin capture enabled:

    bash scripts/probe_output.sh
    copout 1 --json -p > /tmp/copout-output-probe.json
    uv run python scripts/analyze_output_probe.py /tmp/copout-output-probe.json

The analyzer is read-only and does not execute or modify Atuin.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from copout.probe_analysis import analyze_probe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Copout --json output file")
    parser.add_argument("--report", type=Path, help="Save machine-readable analysis here")
    args = parser.parse_args()

    try:
        payload = json.loads(args.capture.read_text(encoding="utf-8"))
        result = analyze_probe(payload)
    except (OSError, ValueError, TypeError) as exc:
        print(f"probe analysis: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.report is not None:
        args.report.write_text(rendered, encoding="utf-8")
    return 0 if result["probe_intact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
