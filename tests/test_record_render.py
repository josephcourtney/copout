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
    assert result["version"] == 5
    assert result["source"] == "atuin"
    assert result["command"] == "pytest"
    assert result["result"]["status"] == 1
    assert result["output"]["text"] == "FAILED\n"
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


def test_render_json_uses_semantic_output_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n   ")],
    )
    rendered = render.render(record.build_record(), as_json=True)
    payload = json.loads(rendered)
    assert payload["history_id"] == "id1"
    assert payload["version"] == 5
    assert payload["source"] == "atuin"
    assert payload["output"]["text"] == "hi"
    assert payload["output"]["utf8_bytes"] == 2


def test_rendered_json_preserves_atuin_output(monkeypatch) -> None:
    original = "hi\n   "
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", original)],
    )
    payload = json.loads(render.render(record.build_record(), as_json=True, mode="rendered"))
    assert payload["output"]["text"] == original
    assert payload["output"]["utf8_bytes"] == len(original.encode())


def test_render_xml_is_compact_semantic_context(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry("id1", "echo <x>", "/tmp", 0, 0.10200000000000001, "", "<x>\n   ")
        ],
    )
    root = ElementTree.fromstring(render.render(record.build_record()))
    assert root.attrib == {"version": "5"}
    run = root.find("run")
    assert run is not None
    assert run.attrib == {"status": "0", "cwd": "/tmp", "duration": "102ms"}
    assert run.findtext("command") == "echo <x>"
    output = run.find("output")
    assert output is not None
    assert output.attrib == {}
    assert output.text == "<x>"


def test_rendered_xml_preserves_capture_metadata(monkeypatch) -> None:
    original = "hello\n   "
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry(
                "id1",
                "printf 'hello\\n'",
                "/tmp",
                0,
                0.1,
                "",
                original,
                output_truncated=False,
                output_observed_bytes=275,
                output_total_bytes=len(original.encode()),
            )
        ],
    )
    root = ElementTree.fromstring(render.render(record.build_record(), mode="rendered"))
    assert root.attrib == {"version": "5", "source": "atuin"}
    run = root.find("run")
    assert run is not None
    assert run.attrib["history_id"] == "id1"
    output = run.find("output")
    assert output is not None
    assert output.text == original
    assert output.attrib["state"] == "captured"
    assert output.attrib["source"] == "atuin-pty-proxy"
    assert output.attrib["utf8_bytes"] == str(len(original.encode()))
    assert output.attrib["observed_bytes"] == "275"


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


def test_unavailable_capture_metadata_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(record, "recent_entries", lambda count: [HistoryEntry("id", "true")])
    output = record.build_record()["output"]
    assert output["truncated"] is None
    assert output["observed_bytes"] is None
    assert output["total_bytes"] is None
