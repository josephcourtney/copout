from __future__ import annotations

from copout.probe_analysis import analyze_probe


def _capture(*, missing: int | None = None, **metadata: object) -> dict:
    lines = ["__COPOUT_PROBE_BEGIN__"]
    lines.extend(
        f"probe {i:04d} {i:072d}"
        for i in range(1, 2401)
        if i != missing
    )
    lines.extend(["__COPOUT_STDERR__", "colored", "ready", "__COPOUT_PROBE_END__"])
    return {
        "version": 9,
        "runs": [{
            "history_id": "probe-id",
            "command": "bash scripts/probe_output.sh",
            "output": {"state": "captured", "text": "\n".join(lines), **metadata},
        }],
    }


def test_exact_probe_is_intact_without_certifying_general_capture() -> None:
    result = analyze_probe(_capture(completeness="unknown", truncated=False))
    assert result["probe_intact"] is True
    assert result["classification"] == "probe-intact"
    assert result["missing_line_count"] == 0
    assert result["line_count_valid"] == 2400
    assert result["markers"]["end"] is True
    assert "not proof" in result["interpretation"]


def test_middle_line_missing_even_if_end_marker_survives() -> None:
    result = analyze_probe(_capture(missing=543, completeness="unknown"))
    assert result["probe_intact"] is False
    assert result["missing_line_indices"] == [543]
    assert result["classification"] == "missing-or-altered-in-retrieved-snapshot"


def test_upstream_truncation_takes_priority() -> None:
    result = analyze_probe(_capture(truncated=True))
    assert result["classification"] == "upstream-reported-incomplete"


def test_copout_presentation_truncation_is_distinct() -> None:
    result = analyze_probe(_capture(presentation_truncated=True))
    assert result["classification"] == "copout-presentation-truncated"


def test_missing_end_marker_is_detected() -> None:
    payload = _capture()
    payload["runs"][0]["output"]["text"] = payload["runs"][0]["output"]["text"].replace(
        "__COPOUT_PROBE_END__", ""
    )
    result = analyze_probe(payload)
    assert result["probe_intact"] is False
    assert result["markers"]["end"] is False


def test_duplicate_probe_line_is_detected() -> None:
    payload = _capture()
    text = payload["runs"][0]["output"]["text"]
    payload["runs"][0]["output"]["text"] = text.replace(
        "probe 0002 000000", "probe 0001 000000", 1
    )
    result = analyze_probe(payload)
    assert result["probe_intact"] is False
    assert result["missing_line_count"] == 1


def test_multi_run_capture_chooses_probe_by_command() -> None:
    payload = _capture()
    payload["runs"].insert(0, {
        "command": "git status",
        "output": {"text": "clean", "state": "captured"},
    })
    assert analyze_probe(payload)["probe_intact"]


def test_invalid_probe_selection_is_explicit() -> None:
    import pytest

    with pytest.raises(ValueError, match="exactly one probe"):
        analyze_probe({"runs": [{"command": "git status"}]})
