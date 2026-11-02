from __future__ import annotations

import json

from copout import record, render
from copout.atuin import HistoryEntry
from copout.edge_probe import CASES, analyze_edge_cases, expected_lines


def _payload() -> dict:
    runs = []
    for case in CASES:
        output = "\n".join(expected_lines(case)) + "\n"
        if case == "redraw":
            output = (
                "__COPOUT_EDGE_REDRAW_BEGIN__\n"
                "download 100%\rready\x1b[K\n"
                "__COPOUT_EDGE_REDRAW_END__\n"
            )
        runs.append(
            HistoryEntry(
                case,
                f"bash scripts/probe_output_edges.sh {case}",
                output=output,
                output_truncated=False,
            )
        )
    return json.loads(render.render(record.build_record_from_entries(runs), as_json=True))


def test_five_edge_probes_survive_actual_copout_normalization() -> None:
    result = analyze_edge_cases(_payload())
    assert result["probe_intact"] is True
    assert result["classification"] == "edge-probes-intact"
    assert result["rapid_order_correct"]
    assert all(case["status"] == "probe-intact" for case in result["cases"].values())


def test_short_command_tail_loss_is_detected() -> None:
    payload = _payload()
    payload["runs"][0]["output"]["text"] = "__COPOUT_EDGE_SHORT_BEGIN__\n"
    result = analyze_edge_cases(payload)
    assert not result["probe_intact"]
    assert result["cases"]["short"]["status"] == "missing-or-altered-output"


def test_final_bytes_before_exit_are_required() -> None:
    payload = _payload()
    payload["runs"][2]["output"]["text"] = "__COPOUT_EDGE_TAIL_BEGIN__"
    assert analyze_edge_cases(payload)["cases"]["tail"]["status"] == "missing-or-altered-output"


def test_rapid_commands_must_remain_separate_and_ordered() -> None:
    payload = _payload()
    payload["runs"][3], payload["runs"][4] = payload["runs"][4], payload["runs"][3]
    result = analyze_edge_cases(payload)
    assert result["rapid_order_correct"] is False
    assert result["probe_intact"] is False


def test_rapid_command_missing_record_is_explicit() -> None:
    payload = _payload()
    payload["runs"].pop()
    result = analyze_edge_cases(payload)
    assert result["cases"]["rapid-b"]["status"] == "missing-or-ambiguous-history"
    assert not result["probe_intact"]


def test_upstream_reported_incomplete_is_not_counted_as_pass() -> None:
    payload = _payload()
    payload["runs"][0]["output"]["exit_capture_complete"] = False
    assert analyze_edge_cases(payload)["probe_intact"] is False


def test_presentation_truncated_is_not_counted_as_pass() -> None:
    payload = _payload()
    payload["runs"][0]["output"]["presentation_truncated"] = True
    assert analyze_edge_cases(payload)["probe_intact"] is False
