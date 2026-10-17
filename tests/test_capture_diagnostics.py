from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

from copout import atuin, capture_diagnostics, cli, record, render

runner = CliRunner()


def _inspect(*entries: atuin.HistoryEntry, requested: int | None = None):
    original = record.build_record_from_entries(list(entries))
    document, projected = render.render_with_projection(original, as_json=True)
    return capture_diagnostics.inspect(original, projected, document, requested=requested)


@pytest.mark.unit
def test_no_defect_does_not_claim_proven_completeness() -> None:
    report = _inspect(atuin.HistoryEntry("id", "echo hi", output="hi\n"), requested=1)

    assert report.status == "no detected loss"
    assert not report.check_failed
    assert report.captured == report.nonempty == 1
    assert report.unavailable == report.omitted_bytes == 0
    assert report.command_bytes == len("echo hi")
    assert report.captured_bytes == report.presented_bytes == 3
    assert "upstream completeness remains unverified" in capture_diagnostics.format_report(report)


@pytest.mark.unit
def test_empty_captured_output_is_not_missing() -> None:
    report = _inspect(atuin.HistoryEntry("id", "true", output=""))
    assert report.captured == 1
    assert report.nonempty == report.unavailable == 0
    assert not report.check_failed


@pytest.mark.unit
def test_unavailable_output_is_partial_even_with_valid_history() -> None:
    report = _inspect(atuin.HistoryEntry("id", "true", output=None, output_error="expired"))
    assert report.status == "partial"
    assert report.check_failed
    assert report.unavailable == 1
    assert ("partial", "output-unavailable") in {
        (issue.severity, issue.code) for issue in report.issues
    }


@pytest.mark.unit
@pytest.mark.parametrize("from_exit", [False, True])
def test_upstream_incomplete_is_partial(from_exit: bool) -> None:
    if from_exit:
        entry = atuin.HistoryEntry("id", "cmd", output="test", output_exit_capture_complete=False)
    else:
        entry = atuin.HistoryEntry("id", "cmd", output="test", output_truncated=True)
    report = _inspect(entry)
    assert report.check_failed
    assert any(issue.code == "upstream-incomplete" for issue in report.issues)


@pytest.mark.unit
def test_pty_traffic_discrepancy_is_advisory_only() -> None:
    report = _inspect(atuin.HistoryEntry("id", "cmd", output="small", output_observed_bytes=1000000))
    assert not report.check_failed
    assert any(issue.code == "upstream-coverage-suspected" for issue in report.issues)


@pytest.mark.unit
def test_utf8_counts_and_per_run_presentation_truncation() -> None:
    entry = atuin.HistoryEntry(
        "id", "printf '🍄'", output="🍄" * (render.MAX_OUTPUT_BYTES_PER_RUN // 4 + 30)
    )
    report = _inspect(entry)
    assert report.check_failed
    assert report.captured_bytes > report.presented_bytes
    assert report.omitted_bytes > 0
    assert any(issue.code == "presentation-truncated" for issue in report.issues)
    assert report.runs[0].command_bytes > len(entry.command)


@pytest.mark.unit
def test_total_budget_truncation_is_detected() -> None:
    entries = [atuin.HistoryEntry(str(i), "cmd", output="x" * (200 * 1024)) for i in range(6)]
    report = _inspect(*entries)
    assert report.check_failed
    assert report.presented_bytes <= render.MAX_OUTPUT_BYTES_TOTAL
    assert sum(issue.code == "presentation-truncated" for issue in report.issues) == 6


@pytest.mark.unit
def test_shortfall_duplicate_and_selected_identity_are_detected() -> None:
    entry = atuin.HistoryEntry("same", "cmd", output="x")
    original = record.build_record_from_entries([entry, entry])
    document, projected = render.render_with_projection(original)
    report = capture_diagnostics.inspect(
        original, projected, document, requested=3, expected_ids=["a", "b"]
    )
    codes = {issue.code for issue in report.issues}
    assert {"selection-shortfall", "duplicate-history-id", "selected-history-id-mismatch"} <= codes
    assert report.status == "invalid"


@pytest.mark.unit
def test_corrupt_raw_byte_count_is_detected() -> None:
    raw = record.build_record_from_entries([atuin.HistoryEntry("x", "cmd", output="é")])
    raw["runs"][0]["output"]["captured_bytes"] = 1
    document, projected = render.render_with_projection(raw)
    report = capture_diagnostics.inspect(raw, projected, document)
    assert report.status == "invalid"
    assert any(issue.code == "captured-byte-count-mismatch" for issue in report.issues)


@pytest.mark.unit
def test_report_has_no_command_or_output_content() -> None:
    report = _inspect(atuin.HistoryEntry("id", "secret-command", output="secret-output"))
    text = capture_diagnostics.format_report(report, verbose=True)
    assert "secret-command" not in text
    assert "secret-output" not in text
    assert "run 1:" in text


@pytest.mark.unit
@pytest.mark.parametrize("format_flag", ["--json", "--markdown", ""])
def test_diagnostics_do_not_modify_printed_document(monkeypatch, format_flag: str) -> None:
    entry = atuin.HistoryEntry("id", "echo hi", output="hello")
    original = record.build_record_from_entries([entry])
    monkeypatch.setattr(cli.record, "build_record", lambda *, context_options: original)
    flags = [format_flag] if format_flag else []
    normal = runner.invoke(cli.app, ["-n", "1", "--print", *flags])
    detailed = runner.invoke(cli.app, ["-n", "1", "--print", "--diagnostics", *flags])
    assert normal.exit_code == detailed.exit_code == 0
    assert normal.stdout == detailed.stdout
    assert normal.stderr == ""
    assert "commands: 1 assembled / 1 requested" in detailed.stderr


@pytest.mark.unit
def test_strict_check_does_not_touch_clipboard_on_partial_capture(monkeypatch) -> None:
    incomplete = record.build_record_from_entries([atuin.HistoryEntry("id", "cmd")])
    monkeypatch.setattr(cli.record, "build_record", lambda *, context_options: incomplete)

    def fail():
        raise AssertionError("clipboard must not start for a rejected capture")

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", fail)
    result = runner.invoke(cli.app, ["-n", "1", "--check"])
    assert result.exit_code == 4
    assert result.stdout == ""
    assert "output-unavailable" in result.stderr


@pytest.mark.unit
def test_strict_check_starts_clipboard_after_success(monkeypatch) -> None:
    complete = record.build_record_from_entries([atuin.HistoryEntry("id", "cmd", output="x")])
    monkeypatch.setattr(cli.record, "build_record", lambda *, context_options: complete)
    writes: list[str] = []

    class Writer:
        def write(self, text: str) -> int:
            writes.append(text)
            return 0

        def abort(self) -> None:
            pass

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", Writer)
    result = runner.invoke(cli.app, ["-n", "1", "--check"])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert len(writes) == 1
    assert "no detected loss" in result.stderr


@pytest.mark.unit
def test_pick_and_root_diagnostics_flags_are_inherited(monkeypatch) -> None:
    observed: list[dict] = []

    def capture(**kwargs) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_pick", capture)
    for args in (
        ["--check", "--diagnostics-verbose", "1"],
        ["pick", "1", "--check", "--diagnostics-verbose"],
    ):
        result = runner.invoke(cli.app, args)
        assert result.exit_code == 0, result.stderr
    assert all(item["check"] and item["diagnostics_verbose"] for item in observed)


@pytest.mark.unit
def test_hydration_identity_mismatch_rejects_selected_capture(monkeypatch) -> None:
    selected = [atuin.HistoryEntry("expected", "cmd", output="x")]
    hydrated = [replace(selected[0], id="changed")]
    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit, *, required_ids=(): selected)
    monkeypatch.setattr(cli.atuin, "hydrate_outputs", lambda entries: hydrated)
    result = runner.invoke(cli.app, ["1", "--check", "--print"])
    assert result.exit_code == 4
    assert result.stdout == ""
    assert "selected-history-id-mismatch" in result.stderr
