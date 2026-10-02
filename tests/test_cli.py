from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from copout import cli, record

runner = CliRunner()


def _record_fixture(*, context_options=None) -> dict:
    del context_options
    return {
        "version": 7,
        "scope": "command",
        "source": "atuin",
        "captured_at": "2026-10-01T09:30:00-04:00",
        "history_id": "abc",
        "command": "echo hi",
        "result": {"status": 0},
        "output": {
            "state": "captured",
            "error": None,
            "source": "atuin-pty-proxy",
            "text": "hi\n",
            "captured_bytes": 3,
            "truncated": False,
            "observed_bytes": 3,
            "total_bytes": 3,
        },
        "context": {"cwd": "/tmp"},
        "timing": {"duration": 0.01},
    }


def test_help_is_available_with_short_option() -> None:
    result = runner.invoke(cli.app, ["-h"])

    assert result.exit_code == 0
    assert "Copy recent structured terminal history from Atuin" in result.stdout
    assert "--print" in result.stdout
    assert "--json" in result.stdout
    assert "--markdown" in result.stdout
    assert "--pretty-attributes" in result.stdout
    assert "--last" in result.stdout
    assert "--failure" in result.stdout
    assert "--limit" in result.stdout
    assert "--preselect" in result.stdout
    assert "--preselect-records" in result.stdout
    assert "--git-context" in result.stdout
    assert "--system-context" in result.stdout
    assert "--hostname-context" in result.stdout
    assert "--rendered" not in result.stdout
    assert "--raw" not in result.stdout


def test_help_is_available_with_long_option() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "positional selectors" in result.stdout


def test_pick_help_describes_preselection() -> None:
    result = runner.invoke(cli.app, ["pick", "--help"])

    assert result.exit_code == 0
    assert "--preselect" in result.stdout
    assert "--preselect-records" in result.stdout
    assert "--git-context" in result.stdout


def test_bare_invocation_opens_picker(monkeypatch) -> None:
    observed = []

    def run_pick(**kwargs) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_pick", run_pick)

    result = runner.invoke(cli.app)

    assert result.exit_code == 0, result.stderr
    assert observed[0]["selectors"] == []
    assert observed[0]["preselect"] == []
    assert observed[0]["limit"] == 100


def test_root_selectors_route_to_noninteractive_selection(monkeypatch) -> None:
    observed = []

    def run_pick(**kwargs) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_pick", run_pick)

    result = runner.invoke(cli.app, ["--markdown", "1", "3-4", "--print"])

    assert result.exit_code == 0, result.stderr
    assert observed[0]["selectors"] == ["1", "3-4"]
    assert observed[0]["preselect"] == []
    assert observed[0]["as_markdown"] is True
    assert observed[0]["print_output"] is True


def test_root_preselect_opens_picker_with_relative_selection(monkeypatch) -> None:
    observed = []

    def run_pick(**kwargs) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_pick", run_pick)

    result = runner.invoke(
        cli.app,
        ["--preselect", "1,3", "--preselect", "5-7", "--preselect-records", "id1,id2"],
    )

    assert result.exit_code == 0, result.stderr
    assert observed[0]["selectors"] == []
    assert observed[0]["preselect"] == ["1,3", "5-7"]
    assert observed[0]["preselect_records"] == ["id1,id2"]


def test_root_rejects_preselect_with_noninteractive_query() -> None:
    result = runner.invoke(cli.app, ["--preselect", "1", "--last", "3"])

    assert result.exit_code == 2
    assert "cannot be combined" in result.stderr


def test_context_cli_overrides_config_defaults(monkeypatch) -> None:
    observed = []

    def build_record(*, context_options) -> dict:
        observed.append(context_options)
        return _record_fixture()

    monkeypatch.setattr(cli.record, "build_record", build_record)

    result = runner.invoke(
        cli.app,
        [
            "--print",
            "--last",
            "1",
            "--no-git-context",
            "--hostname-context",
            "--shell-version",
            "--env",
            "TERM",
            "--resolve",
            "git",
        ],
    )

    assert result.exit_code == 0, result.stderr
    options = observed[0]
    assert options.git is False
    assert options.hostname is True
    assert options.shell_version is True
    assert options.env == ("TERM",)
    assert options.executables == ("git",)


def test_context_cli_overrides_config_file(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "copout.toml"
    config_path.write_text(
        """
[context]
git = true
hostname = false
env = ["LANG"]
executables = ["python"]
""".strip()
    )
    observed = []

    def build_record(*, context_options) -> dict:
        observed.append(context_options)
        return _record_fixture()

    monkeypatch.setattr(cli.record, "build_record", build_record)

    result = runner.invoke(
        cli.app,
        [
            "--config",
            str(config_path),
            "--no-git-context",
            "--hostname-context",
            "--env",
            "TERM",
            "--resolve",
            "git",
            "--print",
            "--last",
            "1",
        ],
    )

    assert result.exit_code == 0, result.stderr
    options = observed[0]
    assert options.git is False
    assert options.hostname is True
    assert options.env == ("LANG", "TERM")
    assert options.executables == ("python", "git")


def test_atuin_failure_goes_to_stderr_and_returns_exit_3(monkeypatch) -> None:
    def fail(*, context_options=None) -> dict:
        del context_options
        raise record.AtuinError("history unavailable")

    monkeypatch.setattr(cli.record, "build_record", fail)

    result = runner.invoke(cli.app, ["--print", "--last", "1"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "copout: history unavailable" in result.stderr
    assert "copout: run `copout doctor` for diagnostics" in result.stderr


def test_clipboard_helper_starts_before_record_build(monkeypatch) -> None:
    events: list[str] = []

    class Writer:
        def write(self, text: str) -> int:
            assert text == "payload"
            events.append("clipboard-write")
            return 0

        def abort(self) -> None:
            pass

    def start_writer() -> Writer:
        events.append("clipboard-start")
        return Writer()

    def build_record(*, context_options=None) -> dict:
        del context_options
        events.append("record-build")
        return {}

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", start_writer)
    monkeypatch.setattr(cli.record, "build_record", build_record)
    monkeypatch.setattr(
        cli.render,
        "render",
        lambda captured, *, as_json, as_markdown, pretty_attributes: "payload",
    )

    result = runner.invoke(cli.app, ["--last", "1"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert events == ["clipboard-start", "record-build", "clipboard-write"]


def test_record_failure_aborts_prestarted_clipboard_helper(monkeypatch) -> None:
    events: list[str] = []

    class Writer:
        def write(self, text: str) -> int:
            raise AssertionError(f"clipboard payload must not be written: {text!r}")

        def abort(self) -> None:
            events.append("clipboard-abort")

    def start_writer() -> Writer:
        events.append("clipboard-start")
        return Writer()

    def fail(*, context_options=None) -> dict:
        del context_options
        events.append("record-build")
        raise record.AtuinError("history unavailable")

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", start_writer)
    monkeypatch.setattr(cli.record, "build_record", fail)

    result = runner.invoke(cli.app, ["--last", "1"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "copout: history unavailable" in result.stderr
    assert events == ["clipboard-start", "record-build", "clipboard-abort"]


def test_print_writes_semantic_result_to_stdout(monkeypatch) -> None:
    monkeypatch.setattr(cli.record, "build_record", _record_fixture)

    def clipboard_must_not_be_started():
        raise AssertionError("clipboard must not be used with --print")

    monkeypatch.setattr(
        cli.clipboard,
        "start_clipboard_writer",
        clipboard_must_not_be_started,
    )

    result = runner.invoke(cli.app, ["--print", "--last", "1"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.startswith('<copout version="7"')
    assert 'source="atuin"' not in result.stdout
    assert "<![CDATA[echo hi]]>" in result.stdout


def test_markdown_cli_and_conflicting_formats(monkeypatch) -> None:
    monkeypatch.setattr(cli.record, "build_record", _record_fixture)
    markdown = runner.invoke(cli.app, ["--markdown", "--print", "--last", "1"])
    assert markdown.exit_code == 0, markdown.stderr
    assert "### Command" in markdown.stdout
    assert "```console\necho hi\n```" in markdown.stdout
    assert "```\nhi\n```" in markdown.stdout

    conflict = runner.invoke(cli.app, ["--json", "--markdown", "--print", "--last", "1"])
    assert conflict.exit_code == 2
    assert "cannot be combined" in conflict.stderr


def test_pretty_attributes_is_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(cli.record, "build_record", _record_fixture)

    result = runner.invoke(cli.app, ["--print", "--pretty-attributes", "--last", "1"])

    assert result.exit_code == 0, result.stderr
    assert '<run\n    status="0"\n    cwd="/tmp"\n    duration_ms="10">' in result.stdout


def test_json_print_emits_valid_json(monkeypatch) -> None:
    monkeypatch.setattr(cli.record, "build_record", _record_fixture)

    result = runner.invoke(cli.app, ["--print", "--json", "--last", "1"])

    assert result.exit_code == 0
    assert '"history_id": "abc"' in result.stdout
    assert '"scope": "command"' in result.stdout


def test_last_rejects_zero() -> None:
    result = runner.invoke(cli.app, ["--last", "0"])

    assert result.exit_code != 0
    assert "0" in result.stderr


def test_install_command_has_been_removed() -> None:
    result = runner.invoke(cli.app, ["install"])

    assert result.exit_code != 0
