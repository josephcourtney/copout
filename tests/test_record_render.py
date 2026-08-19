from __future__ import annotations

import json

from copout import record, render
from copout.atuin import HistoryEntry


def test_build_record(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "previous_entry",
        lambda: HistoryEntry("id1", "pytest", "/work", 1, 2.5, "2026-08-19T10:00:00Z", "FAILED\n"),
    )
    result = record.build_record()
    assert result["command"] == "pytest"
    assert result["result"]["status"] == 1
    assert result["output"]["text"] == "FAILED\n"
    assert result["capture"]["history_source"] == "atuin"


def test_render_json(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "previous_entry",
        lambda: HistoryEntry("id1", "echo hi", "/tmp", 0, 0.1, "", "hi\n"),
    )
    rendered = render.render(record.build_record(), as_json=True)
    payload = json.loads(rendered)
    assert payload["history_id"] == "id1"


def test_render_xml_contains_command_and_output(monkeypatch) -> None:
    monkeypatch.setattr(
        record,
        "previous_entry",
        lambda: HistoryEntry("id1", "echo <x>", "/tmp", 0, 0.1, "", "<x>\n"),
    )
    rendered = render.render(record.build_record())
    assert 'source="atuin"' in rendered
    assert "<![CDATA[echo <x>]]>" in rendered
    assert "<![CDATA[<x>\n]]>" in rendered
