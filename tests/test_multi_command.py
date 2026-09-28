from __future__ import annotations

import json
from xml.etree import ElementTree

from typer.testing import CliRunner

from copout import atuin, cli, record, render
from copout.atuin import HistoryEntry

runner = CliRunner()


def test_recent_history_does_not_fetch_output(monkeypatch) -> None:
    entry = HistoryEntry("1", "echo hi")
    monkeypatch.setattr(atuin, "_load_history", lambda: [entry])

    async def fail_outputs(selected: list[HistoryEntry]) -> list[HistoryEntry]:
        del selected
        raise AssertionError("candidate discovery must not fetch output")

    monkeypatch.setattr(atuin, "_add_outputs", fail_outputs)

    assert atuin.recent_history(20) == [entry]


def test_hydrate_outputs_fetches_only_supplied_entries(monkeypatch) -> None:
    calls: list[str] = []

    async def add_outputs(selected: list[HistoryEntry]) -> list[HistoryEntry]:
        calls.extend(entry.id for entry in selected)
        return selected

    monkeypatch.setattr(atuin, "_add_outputs", add_outputs)
    entries = [HistoryEntry("3", "three"), HistoryEntry("1", "one")]

    assert atuin.hydrate_outputs(entries) == entries
    assert calls == ["3", "1"]


def test_pick_explicit_selectors_are_noninteractive(monkeypatch) -> None:
    entries = [
        HistoryEntry("3", "newest", output="new\n"),
        HistoryEntry("2", "middle", output="middle\n"),
        HistoryEntry("1", "oldest", output="old\n"),
    ]
    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit: entries)
    monkeypatch.setattr(cli.atuin, "hydrate_outputs", lambda selected: selected)

    def must_not_prompt(candidates: list[HistoryEntry]) -> list[str]:
        del candidates
        raise AssertionError("must not prompt")

    monkeypatch.setattr(cli.selection, "prompt_selection", must_not_prompt)

    result = runner.invoke(cli.app, ["pick", "1", "3", "--print"])

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.index("oldest") < result.stdout.index("newest")
    assert "middle" not in result.stdout


def test_pick_without_selectors_uses_prompt(monkeypatch) -> None:
    entries = [HistoryEntry("2", "newest"), HistoryEntry("1", "oldest")]
    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit: entries)
    monkeypatch.setattr(cli.atuin, "hydrate_outputs", lambda selected: selected)
    monkeypatch.setattr(cli.selection, "prompt_selection", lambda candidates: ["2"])

    result = runner.invoke(cli.app, ["pick", "--print"])

    assert result.exit_code == 0, result.stderr
    assert "oldest" in result.stdout
    assert "newest" not in result.stdout


def test_pick_rejects_out_of_window_selector(monkeypatch) -> None:
    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit: [HistoryEntry("1", "one")])

    result = runner.invoke(cli.app, ["pick", "2", "--print"])

    assert result.exit_code == 2
    assert "outside the 1 available commands" in result.stderr


def test_pick_hydrates_only_selected_entries(monkeypatch) -> None:
    entries = [HistoryEntry(str(index), f"cmd {index}") for index in range(5, 0, -1)]
    hydrated_ids: list[str] = []
    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit: entries)

    def hydrate(selected: list[HistoryEntry]) -> list[HistoryEntry]:
        hydrated_ids.extend(entry.id for entry in selected)
        return selected

    monkeypatch.setattr(cli.atuin, "hydrate_outputs", hydrate)

    result = runner.invoke(cli.app, ["pick", "1", "4", "--print"])

    assert result.exit_code == 0, result.stderr
    assert hydrated_ids == ["2", "5"]


def test_history_output_is_bounded_and_marked() -> None:
    text = "a" * (render.MAX_OUTPUT_BYTES_PER_RUN + 1000)
    history = record.build_history_from_entries([HistoryEntry("id", "build", output=text)])
    payload = json.loads(render.render(history, as_json=True))
    output = payload["runs"][0]["output"]

    assert output["presentation_truncated"] is True
    assert output["presentation_omitted_bytes"] > 0
    assert output["utf8_bytes"] <= render.MAX_OUTPUT_BYTES_PER_RUN
    assert "copout omitted" in output["text"]


def test_history_total_output_budget_is_shared() -> None:
    entries = [
        HistoryEntry(str(index), f"cmd {index}", output="x" * (200 * 1024))
        for index in range(6)
    ]
    payload = json.loads(render.render(record.build_history_from_entries(entries), as_json=True))
    sizes = [run["output"]["utf8_bytes"] for run in payload["runs"]]

    assert sum(sizes) <= render.MAX_OUTPUT_BYTES_TOTAL
    assert max(sizes) <= render.MAX_OUTPUT_BYTES_PER_RUN
    assert all(run["output"]["presentation_truncated"] for run in payload["runs"])


def test_single_command_output_is_not_presentation_bounded(monkeypatch) -> None:
    text = "x" * (render.MAX_OUTPUT_BYTES_PER_RUN + 1000)
    monkeypatch.setattr(
        record, "recent_entries", lambda count: [HistoryEntry("id", "cmd", output=text)]
    )

    payload = json.loads(render.render(record.build_record(), as_json=True))

    assert payload["output"]["text"] == text
    assert "presentation_truncated" not in payload["output"]


def test_history_utf8_truncation_does_not_split_codepoints() -> None:
    text = "🍄" * 40000
    history = record.build_history_from_entries([HistoryEntry("id", "mushrooms", output=text)])
    payload = json.loads(render.render(history, as_json=True))
    output = payload["runs"][0]["output"]

    assert output["text"].encode("utf-8").decode("utf-8") == output["text"]
    assert output["utf8_bytes"] <= render.MAX_OUTPUT_BYTES_PER_RUN


def test_xml_reports_presentation_truncation_separately() -> None:
    text = "x" * (render.MAX_OUTPUT_BYTES_PER_RUN + 1000)
    history = record.build_history_from_entries([HistoryEntry("id", "build", output=text)])

    output = ElementTree.fromstring(render.render(history)).find("run/output")

    assert output is not None
    assert output.attrib["presentation_truncated"] == "true"
    assert int(output.attrib["presentation_omitted_bytes"]) > 0
    assert "truncated" not in output.attrib
