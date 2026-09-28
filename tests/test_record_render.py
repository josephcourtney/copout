from __future__ import annotations

import json
from xml.etree import ElementTree

from copout import record, render
from copout.atuin import AtuinError, HistoryEntry


def test_build_record(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry(
                "id1",
                "pytest",
                "/work",
                1,
                2.5,
                "2026-08-19T10:00:00Z",
                "FAILED\n",
            )
        ],
    )
    result = record.build_record()
    assert result["version"] == 6
    assert result["source"] == "atuin"
    assert result["command"] == "pytest"
    assert result["result"]["status"] == 1
    assert result["output"]["text"] == "FAILED\n"
    assert result["output"]["captured_bytes"] == len("FAILED\n".encode())
    assert "capture" not in result


def test_build_record_rejects_empty_history(monkeypatch) -> None:
    monkeypatch.setattr(record, "recent_entries", lambda count: [])

    try:
        record.build_record()
    except AtuinError as exc:
        assert "no previous non-copout command" in str(exc)
    else:
        raise AssertionError("expected AtuinError")


def test_build_history_reports_output_count_without_redundant_capture_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count, *, failed_only=False: [
            HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n"),
            HistoryEntry("id2", "true", "/tmp", 0, 0.1, "", None),
        ],
    )

    result = record.build_history(count=2)

    assert result["source"] == "atuin"
    assert result["history"]["outputs_available"] == 1
    assert "capture" not in result
    assert [run["output"]["source"] for run in result["runs"]] == [
        "atuin-history-only",
        "atuin-pty-proxy",
    ]


def test_render_json_uses_semantic_output(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n   ")],
    )
    rendered = render.render(record.build_record(), as_json=True)
    payload = json.loads(rendered)
    assert payload["history_id"] == "id1"
    assert payload["version"] == 6
    assert payload["source"] == "atuin"
    assert payload["output"]["text"] == "hi"
    assert payload["output"]["captured_bytes"] == 2
    assert "utf8_bytes" not in payload["output"]


def test_render_xml_is_compact_semantic_context(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry("id1", "echo <x>", "/tmp", 0, 0.10200000000000001, "", "<x>\n   ")
        ],
    )
    root = ElementTree.fromstring(render.render(record.build_record()))
    assert root.attrib == {"version": "6"}
    run = root.find("run")
    assert run is not None
    assert run.attrib == {"status": "0", "cwd": "/tmp", "duration_ms": "102"}
    assert run.findtext("command") == "echo <x>"
    output = run.find("output")
    assert output is not None
    assert output.attrib == {}
    assert output.text == "<x>"


def test_history_xml_omits_redundant_selected_attribute() -> None:
    history = record.build_history_from_entries(
        [HistoryEntry("id", "echo hi", output="hi\n")]
    )
    root = ElementTree.fromstring(render.render(history))
    assert root.attrib == {"version": "6"}
    assert len(root.findall("run")) == 1


def test_xml_attribute_pretty_printing_is_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id", "echo hi", "/tmp", 0, 0.121, "", "hi\n")],
    )
    compact = render.render(record.build_record())
    pretty = render.render(record.build_record(), pretty_attributes=True)

    assert '<run status="0" cwd="/tmp" duration_ms="121">' in compact
    assert '<run\n    status="0"\n    cwd="/tmp"\n    duration_ms="121">' in pretty


def test_xml_round_trips_controls_and_attribute_whitespace(monkeypatch) -> None:
    command = "printf '\x00\x1b'\r\n]]>"
    cwd = "/tmp/tab\tnewline\ncarriage\rcontrol\x01"
    output = "\x00\x01\x1b\ufffe\uffff\r\n]]> café"
    monkeypatch.setattr(
        record, "recent_entries", lambda count: [HistoryEntry("id", command, cwd, output=output)]
    )
    root = ElementTree.fromstring(render.render(record.build_record()))
    run = root.find("run")
    assert run is not None
    assert run.attrib["cwd_encoding"] == "json-string"
    assert json.loads(run.attrib["cwd"]) == cwd
    for name, expected in (("command", command), ("output", output)):
        element = run.find(name)
        assert element is not None
        assert element.attrib["encoding"] == "json-string"
        assert json.loads(element.text or "") == expected


def test_xml_plain_text_and_cdata_terminator_round_trip(monkeypatch) -> None:
    text = "café\n\t]]> & < >"
    monkeypatch.setattr(
        record, "recent_entries", lambda count: [HistoryEntry("id", text, output=text)]
    )
    root = ElementTree.fromstring(render.render(record.build_record()))
    for name in ("command", "output"):
        element = root.find(f"run/{name}")
        assert element is not None
        assert "encoding" not in element.attrib
        assert element.text == text


def test_normal_capture_metadata_stays_sparse(monkeypatch) -> None:
    entry = HistoryEntry(
        "id",
        "echo hi",
        output="hi\n",
        output_truncated=False,
        output_observed_bytes=3,
        output_total_bytes=3,
        output_exit_capture_complete=True,
    )
    monkeypatch.setattr(record, "recent_entries", lambda count: [entry])

    output = ElementTree.fromstring(render.render(record.build_record())).find("run/output")

    assert output is not None
    assert output.attrib == {}


def test_extended_capture_metadata_is_emitted_for_incomplete_output(monkeypatch) -> None:
    entry = HistoryEntry(
        "id",
        "build",
        output="hello\n",
        output_truncated=True,
        output_observed_bytes=24,
        output_total_bytes=30,
        output_exit_capture_complete=False,
    )
    monkeypatch.setattr(record, "recent_entries", lambda count: [entry])

    output = ElementTree.fromstring(render.render(record.build_record())).find("run/output")

    assert output is not None
    assert output.attrib == {
        "truncated": "true",
        "captured_bytes": "5",
        "observed_bytes": "24",
        "total_bytes": "30",
        "exit_capture_complete": "false",
    }


def test_unavailable_capture_metadata_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(record, "recent_entries", lambda count: [HistoryEntry("id", "true")])
    output = record.build_record()["output"]
    assert output["truncated"] is None
    assert output["observed_bytes"] is None
    assert output["total_bytes"] is None
    assert "exit_capture_complete" not in output
