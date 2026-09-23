from __future__ import annotations

from typer.testing import CliRunner

from copout import cli, record

runner = CliRunner()


def test_help_is_available_with_short_option() -> None:
    result = runner.invoke(cli.app, ["-h"])

    assert result.exit_code == 0
    assert "Copy recent structured terminal history from Atuin" in result.stdout
    assert "--print" in result.stdout
    assert "--json" in result.stdout
    assert "--last" in result.stdout
    assert "--failure" in result.stdout


def test_help_is_available_with_long_option() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "Copy recent structured terminal history from Atuin" in result.stdout


def test_atuin_failure_goes_to_stderr_and_returns_exit_3(monkeypatch) -> None:
    def fail() -> dict:
        raise record.AtuinError("history unavailable")

    monkeypatch.setattr(cli.record, "build_record", fail)

    result = runner.invoke(cli.app, ["--print"])

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

    def build_record() -> dict:
        events.append("record-build")
        return {}

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", start_writer)
    monkeypatch.setattr(cli.record, "build_record", build_record)
    monkeypatch.setattr(cli.render, "render", lambda captured, *, as_json: "payload")

    result = runner.invoke(cli.app)

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

    def fail() -> dict:
        events.append("record-build")
        raise record.AtuinError("history unavailable")

    monkeypatch.setattr(cli.clipboard, "start_clipboard_writer", start_writer)
    monkeypatch.setattr(cli.record, "build_record", fail)

    result = runner.invoke(cli.app)

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "copout: history unavailable" in result.stderr
    assert events == ["clipboard-start", "record-build", "clipboard-abort"]


def test_print_writes_rendered_result_to_stdout(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.record,
        "build_record",
        lambda: {
            "version": 4,
            "scope": "command",
            "source": "atuin",
            "history_id": "abc",
            "command": "echo hi",
            "result": {"status": 0},
            "output": {
                "state": "captured",
                "error": None,
                "source": "atuin-pty-proxy",
                "text": "hi\n",
                "utf8_bytes": 3,
                "truncated": False,
                "observed_bytes": 3,
                "total_bytes": 3,
            },
            "context": {"cwd": "/tmp"},
            "timing": {"duration": 0.01},
        },
    )

    def clipboard_must_not_be_started():
        raise AssertionError("clipboard must not be used with --print")

    monkeypatch.setattr(
        cli.clipboard,
        "start_clipboard_writer",
        clipboard_must_not_be_started,
    )

    result = runner.invoke(cli.app, ["--print"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.startswith('<copout version="4"')
    assert "<![CDATA[echo hi]]>" in result.stdout


def test_json_print_emits_valid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.record,
        "build_record",
        lambda: {
            "version": 4,
            "scope": "command",
            "source": "atuin",
            "history_id": "abc",
            "command": "true",
            "result": {"status": 0},
            "output": {
                "state": "captured",
                "error": None,
                "source": "atuin-pty-proxy",
                "text": "",
                "utf8_bytes": 0,
                "truncated": False,
                "observed_bytes": 0,
                "total_bytes": 0,
            },
            "context": {"cwd": "/tmp"},
            "timing": {"duration": 0.01},
        },
    )

    result = runner.invoke(cli.app, ["--print", "--json"])

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
