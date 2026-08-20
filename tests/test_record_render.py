from __future__ import annotations

import json

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
    assert result["version"] == 3
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


def test_render_json(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n")],
    )
    rendered = render.render(record.build_record(), as_json=True)
    payload = json.loads(rendered)
    assert payload["history_id"] == "id1"
    assert payload["version"] == 3
    assert payload["source"] == "atuin"


def test_render_xml_contains_command_and_output(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "recent_entries",
        lambda count: [HistoryEntry("id1", "echo <x>", "/tmp", 0, 0.1, "", "<x>\n")],
    )
    rendered = render.render(record.build_record())
    assert 'source="atuin"' in rendered
    assert "<![CDATA[echo <x>]]>" in rendered
    assert "<![CDATA[<x>\n]]>" in rendered
