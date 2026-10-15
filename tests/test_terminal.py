from __future__ import annotations

import json
from xml.etree import ElementTree

import pytest

from copout import record, render
from copout.atuin import HistoryEntry
from copout.terminal import plain_terminal_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\x1b[32m+\x1b[m \x1b[1mmlx\x1b[2m==0.32.2\n", "+ mlx==0.32.2"),
        ("download 100%\rready\x1b[K\n", "ready"),
        ("abc\bZ\n", "abZ"),
        ("top\nbottom\x1b[1A\rnew\x1b[K", "new\nbottom"),
        ("\x1b]8;;https://example.org\x1b\\title\x1b]8;;\x1b\\", "title"),
        ("\x1b]0;title\x07content", "content"),
        ("hi\x00\x01\ufffe", r"hi\x00\x01\ufffe"),
        ("start\x1b[2Jend", "end"),
        ("café\n\tindented", "café\n        indented"),
    ],
)
def test_plain_terminal_golden(raw: str, expected: str) -> None:
    assert plain_terminal_text(raw) == expected


def test_all_formats_share_safe_text_without_losing_capture_provenance() -> None:
    source = "\x1b[32mfirst\x1b[m\rSECOND\x1b[K\n"
    entry = HistoryEntry(
        "id",
        "printf output",
        output=source,
        output_truncated=False,
        output_observed_bytes=540_905,
    )
    captured = record.build_record_from_entries([entry])
    raw_bytes = len(source.encode())

    payload = json.loads(render.render(captured, as_json=True))
    output = payload["runs"][0]["output"]
    assert payload["version"] == 9
    assert output["text"] == "SECOND"
    assert output["captured_bytes"] == raw_bytes
    assert output["presented_bytes"] == len("SECOND".encode())
    assert output["truncated"] is False
    assert output["completeness"] == "unknown"
    assert output["coverage_warning"] == "rendered-snapshot-much-smaller-than-pty-traffic"

    xml = ElementTree.fromstring(render.render(captured)).find("run/output")
    assert xml is not None
    assert xml.text == output["text"]
    assert xml.attrib["completeness"] == "unknown"
    assert "encoding" not in xml.attrib

    markdown = render.render(captured, as_markdown=True)
    assert "SECOND" in markdown
    assert "\x1b" not in markdown
    assert "earlier terminal output may be missing" in markdown


def test_upstream_failure_does_not_become_successful_capture() -> None:
    entry = HistoryEntry(
        "id",
        "long",
        output="tail",
        output_truncated=False,
        output_exit_capture_complete=False,
    )
    payload = json.loads(
        render.render(record.build_record_from_entries([entry]), as_json=True)
    )
    assert payload["runs"][0]["output"]["completeness"] == "incomplete"
    assert payload["runs"][0]["output"]["exit_capture_complete"] is False


def test_presentation_budget_does_not_change_source_capture_size() -> None:
    source = "x" * (render.MAX_OUTPUT_BYTES_PER_RUN * 2)
    payload = json.loads(
        render.render(
            record.build_record_from_entries([HistoryEntry("id", "large", output=source)]),
            as_json=True,
        )
    )
    output = payload["runs"][0]["output"]
    assert output["captured_bytes"] == len(source)
    assert output["presented_bytes"] <= render.MAX_OUTPUT_BYTES_PER_RUN
    assert output["presentation_truncated"] is True
    assert output["presentation_omitted_bytes"] > 0
    assert output["completeness"] == "unknown"
