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
    assert result["version"] == 8
    assert result["source"] == "atuin"
    assert "scope" not in result
    assert "history" not in result
    assert len(result["runs"]) == 1
    run = result["runs"][0]
    assert run["history_id"] == "id1"
    assert run["command"] == "pytest"
    assert run["result"]["status"] == 1
    assert run["output"]["text"] == "FAILED\n"
    assert run["output"]["captured_bytes"] == len(b"FAILED\n")
    assert "capture" not in result


def test_single_run_builders_share_the_same_envelope(monkeypatch) -> None:
    entry = HistoryEntry("id", "echo hi", "/tmp", 0, 0.1, "", "hi\n")
    monkeypatch.setattr(record, "recent_entries", lambda count, *, failed_only=False: [entry])

    latest = record.build_record()
    counted = record.build_history(count=1)
    selected = record.build_record_from_entries([entry])

    assert latest.keys() == counted.keys() == selected.keys()
    assert latest["runs"] == counted["runs"] == selected["runs"]
    assert "scope" not in latest
    assert "history" not in latest


def test_build_record_rejects_empty_history(monkeypatch) -> None:
    monkeypatch.setattr(record, "recent_entries", lambda count: [])

    try:
        record.build_record()
    except AtuinError as exc:
        assert "no previous non-copout command" in str(exc)
    else:
        raise AssertionError("expected AtuinError")


def test_build_history_uses_same_universal_envelope(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count, *, failed_only=False: [
            HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n"),
            HistoryEntry("id2", "true", "/tmp", 0, 0.1, "", None),
        ],
    )

    result = record.build_history(count=2)

    assert result["version"] == 8
    assert result["source"] == "atuin"
    assert "scope" not in result
    assert "history" not in result
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
    assert payload["version"] == 8
    assert payload["source"] == "atuin"
    assert "scope" not in payload
    assert "history" not in payload
    assert len(payload["runs"]) == 1
    run = payload["runs"][0]
    assert run["history_id"] == "id1"
    assert run["output"]["text"] == "hi"
    assert run["output"]["captured_bytes"] == 2
    assert "utf8_bytes" not in run["output"]


def test_render_xml_is_compact_semantic_context(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry("id1", "echo <x>", "/tmp", 0, 0.10200000000000001, "", "<x>\n   ")
        ],
    )
    root = ElementTree.fromstring(render.render(record.build_record()))
    assert root.attrib["version"] == "8"
    assert "captured_at" in root.attrib
    run = root.find("run")
    assert run is not None
    assert run.attrib == {
        "history_id": "id1",
        "status": "0",
        "cwd": "/tmp",
        "duration_ms": "102",
    }
    assert run.findtext("command") == "echo <x>"
    output = run.find("output")
    assert output is not None
    assert output.attrib == {}
    assert output.text == "<x>"


def test_one_run_xml_uses_same_envelope_and_includes_history_id() -> None:
    captured = record.build_record_from_entries([HistoryEntry("id", "echo hi", output="hi\n")])
    root = ElementTree.fromstring(render.render(captured))
    assert root.attrib["version"] == "8"
    assert "captured_at" in root.attrib
    runs = root.findall("run")
    assert len(runs) == 1
    assert runs[0].attrib["history_id"] == "id"


def test_xml_attribute_pretty_printing_is_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id", "echo hi", "/tmp", 0, 0.121, "", "hi\n")],
    )
    compact = render.render(record.build_record())
    pretty = render.render(record.build_record(), pretty_attributes=True)

    assert '<run history_id="id" status="0" cwd="/tmp" duration_ms="121">' in compact
    assert (
        "<run\n"
        '    history_id="id"\n'
        '    status="0"\n'
        '    cwd="/tmp"\n'
        '    duration_ms="121">' in pretty
    )


def test_xml_exposes_recorded_at(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [
            HistoryEntry("id", "echo hi", "/tmp", 0, 0.1, "2026-10-01T09:30:00-04:00", "hi\n")
        ],
    )

    run = ElementTree.fromstring(render.render(record.build_record())).find("run")

    assert run is not None
    assert run.attrib["recorded_at"] == "2026-10-01T09:30:00-04:00"


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
    output = record.build_record()["runs"][0]["output"]
    assert output["truncated"] is None
    assert output["observed_bytes"] is None
    assert output["total_bytes"] is None
    assert "exit_capture_complete" not in output


def test_markdown_uses_safe_fences_and_reports_output_states() -> None:
    entries = [
        HistoryEntry("1", "printf '```'", "/tmp/`\nnext", 0, 0.1, output="a\n````\nb"),
        HistoryEntry("2", "false", output=None, output_error="daemon\nfailed"),
        HistoryEntry("3", "build", output="partial", output_truncated=True),
    ]
    markdown = render.render(record.build_record_from_entries(entries), as_markdown=True)

    assert "`````\na\n````\nb\n`````" in markdown
    assert 'cwd ``"/tmp/`\\nnext"``' in markdown
    assert "Output unavailable." in markdown
    assert 'Output retrieval error: `"daemon\\nfailed"`' in markdown
    assert "Note: Atuin truncated the captured output." in markdown
    assert markdown.index("### Run 1") < markdown.index("### Run 2")


def test_markdown_reports_presentation_truncation() -> None:
    entry = HistoryEntry("1", "build", output="x" * (render.MAX_OUTPUT_BYTES_PER_RUN + 100))
    markdown = render.render(record.build_record_from_entries([entry]), as_markdown=True)

    assert "Note: Copout omitted " in markdown
    assert "[copout omitted" in markdown
