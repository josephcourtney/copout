"""Read-only analysis of the existing 2,400-line terminal-output probe.

A match proves only that this particular known-output probe survived retrieval
and Copout presentation. It does NOT certify general PTY transcript completeness.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

PROBE_COUNT = 2400
_LINE = re.compile(r"^probe ([0-9]{4}) ([0-9]{72})$")
_BEGIN = "__COPOUT_PROBE_BEGIN__"
_END = "__COPOUT_PROBE_END__"


def analyze_probe(capture: dict[str, Any]) -> dict[str, Any]:
    runs = capture.get("runs")
    if not isinstance(runs, list):
        raise ValueError("expected a Copout JSON envelope containing runs")
    # Search by the command, not by run index: Copout may be asked for several runs.
    matches = [
        run
        for run in runs
        if isinstance(run, dict) and "scripts/probe_output.sh" in str(run.get("command", ""))
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one probe command, found {len(matches)}")
    run = matches[0]
    output = run.get("output")
    if not isinstance(output, dict):
        raise ValueError("probe run has no structured output")
    text = output.get("text")
    if not isinstance(text, str):
        raise ValueError("probe output.text must be a string")
    lines = text.splitlines()
    seen: Counter[int] = Counter()
    malformed: list[str] = []
    for line in lines:
        if not line.startswith("probe "):
            continue
        match = _LINE.fullmatch(line)
        if match is None:
            malformed.append(line[:120])
            continue
        index = int(match.group(1))
        if not 1 <= index <= PROBE_COUNT or match.group(2) != f"{index:072d}":
            malformed.append(line[:120])
            continue
        seen[index] += 1
    missing = [number for number in range(1, PROBE_COUNT + 1) if not seen[number]]
    duplicates = [number for number in sorted(seen) if seen[number] > 1]
    boundaries = {
        "begin": _BEGIN in lines,
        "end": _END in lines,
        "stderr": "__COPOUT_STDERR__" in lines,
        "colored": "colored" in lines,
        "redraw_final": "ready" in lines,
    }
    presented_truncated = output.get("presentation_truncated") is True
    upstream_incomplete = (
        output.get("truncated") is True
        or output.get("exit_capture_complete") is False
        or output.get("completeness") == "incomplete"
    )
    pass_probe = (
        len(missing) == 0
        and not duplicates
        and not malformed
        and all(boundaries.values())
        and not presented_truncated
        and not upstream_incomplete
    )
    if presented_truncated:
        classification = "copout-presentation-truncated"
    elif output.get("state") == "unavailable":
        classification = "upstream-unavailable"
    elif upstream_incomplete:
        classification = "upstream-reported-incomplete"
    elif pass_probe:
        classification = "probe-intact"
    else:
        classification = "missing-or-altered-in-retrieved-snapshot"
    return {
        "history_id": run.get("history_id"),
        "classification": classification,
        "probe_intact": pass_probe,
        "line_count_expected": PROBE_COUNT,
        "line_count_valid": sum(seen.values()),
        "missing_line_count": len(missing),
        "missing_line_indices": missing[:40],
        "duplicate_line_indices": duplicates[:40],
        "malformed_lines": malformed[:10],
        "markers": boundaries,
        "capture_metadata": {
            key: output.get(key)
            for key in (
                "state",
                "source",
                "completeness",
                "truncated",
                "exit_capture_complete",
                "observed_bytes",
                "captured_bytes",
                "presented_bytes",
                "presentation_truncated",
                "presentation_omitted_bytes",
                "coverage_warning",
            )
            if key in output
        },
        "interpretation": (
            "The known probe is intact in the retrieved and presented output; "
            "this is not proof of general transcript completeness."
            if pass_probe
            else "This analysis cannot determine whether missing data arose in the "
            "Atuin PTY capture, retained rendering, daemon retrieval, or Copout "
            "normalization without comparing lower-layer evidence."
        ),
    }
