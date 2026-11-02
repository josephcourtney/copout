#!/usr/bin/env python3
"""Analyze a Copout JSON capture containing all five edge probes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from copout.edge_probe import analyze_edge_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--report", type=Path, help="Write JSON analysis to this path")
    args = parser.parse_args()
    try:
        result = analyze_edge_cases(json.loads(args.capture.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        print(f"edge probe analysis: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    return 0 if result["probe_intact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
