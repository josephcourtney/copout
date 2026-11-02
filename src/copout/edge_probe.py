"""Deterministic short-output, redraw, rapid-command, and exit-tail probes.

Emit one case per shell command, then inspect the five resulting Copout runs.
This reports known-output preservation, not general transcript completeness.
"""

from __future__ import annotations

from typing import Any

CASES = ("short", "redraw", "tail", "rapid-a", "rapid-b")
PREFIX = "__COPOUT_EDGE_"


def expected_lines(case: str) -> list[str]:
    if case not in CASES:
        raise ValueError(f"unknown probe case: {case}")
    token = case.upper().replace("-", "_")
    middle = {
        "short": "On branch feature/edge-probe\nworking tree clean",
        "redraw": "ready",
        "tail": "tail-flushed-before-exit",
        "rapid-a": "rapid-first",
        "rapid-b": "rapid-second",
    }[case]
    return [f"{PREFIX}{token}_BEGIN__", *middle.splitlines(), f"{PREFIX}{token}_END__"]


def analyze_edge_cases(payload: dict[str, Any]) -> dict[str, Any]:
    """Locate each exact probe command and verify expected normalized output."""
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ValueError("expected a Copout JSON envelope with a runs array")

    by_case: dict[str, list[dict[str, Any]]] = {case: [] for case in CASES}
    for run in runs:
        if not isinstance(run, dict):
            continue
        command = run.get("command")
        if not isinstance(command, str):
            continue
        for case in CASES:
            # Require a full single-command invocation to avoid matching
            # unrelated command arguments or analysis commands.
            if command.strip() in (
                f"bash scripts/probe_output_edges.sh {case}",
                f"./scripts/probe_output_edges.sh {case}",
            ):
                by_case[case].append(run)

    results: dict[str, dict[str, Any]] = {}
    for case in CASES:
        matches = by_case[case]
        if len(matches) != 1:
            results[case] = {"status": "missing-or-ambiguous-history", "matches": len(matches)}
            continue
        run = matches[0]
        output = run.get("output")
        if not isinstance(output, dict) or not isinstance(output.get("text"), str):
            results[case] = {"status": "missing-output", "history_id": run.get("history_id")}
            continue
        lines = output["text"].splitlines()
        expected = expected_lines(case)
        metadata = {
            key: output[key]
            for key in ("completeness", "truncated", "exit_capture_complete",
                        "observed_bytes", "captured_bytes", "presented_bytes",
                        "presentation_truncated", "coverage_warning")
            if key in output
        }
        intact = (
            lines == expected
            and output.get("state") == "captured"
            and output.get("truncated") is not True
            and output.get("exit_capture_complete") is not False
            and output.get("presentation_truncated") is not True
        )
        results[case] = {
            "status": "probe-intact" if intact else "missing-or-altered-output",
            "history_id": run.get("history_id"),
            "expected_lines": expected,
            "actual_lines": lines[:20] if not intact else None,
            "capture_metadata": metadata,
        }

    rapid_a = by_case["rapid-a"]
    rapid_b = by_case["rapid-b"]
    rapid_order = (
        len(rapid_a) == len(rapid_b) == 1
        and runs.index(rapid_a[0]) < runs.index(rapid_b[0])
    )
    passed = rapid_order and all(
        result["status"] == "probe-intact" for result in results.values()
    )
    return {
        "classification": "edge-probes-intact" if passed else "edge-probe-anomaly",
        "probe_intact": passed,
        "rapid_order_correct": rapid_order,
        "cases": results,
        "interpretation": (
            "All five known-output probes survived retrieval and presentation; "
            "this does not establish general PTY transcript completeness."
            if passed else
            "An anomaly was observed in a known-output probe. Compare the "
            "Atuin retained snapshot and lower-layer evidence before attribution."
        ),
    }
