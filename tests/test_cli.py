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


def test_print_writes_rendered_result_to_stdout(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.record,
        "build_record",
        lambda: {
            "version": 2,
            "scope": "command",
            "history_id": "abc",
            "command": "echo hi",
            "result": {"status": 0},
            "output": {
                "state": "captured",
                "source": "atuin-pty-proxy",
                "text": "hi\n",
            },
            "context": {"cwd": "/tmp"},
            "timing": {"duration": 0.01},
        },
    )

    def clipboard_must_not_be_called(text: str) -> int:
        raise AssertionError("clipboard must not be used with --print")

    monkeypatch.setattr(
        cli.clipboard,
        "copy_to_clipboard",
        clipboard_must_not_be_called,
    )

    result = runner.invoke(cli.app, ["--print"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.startswith('<copout version="2"')
    assert "<![CDATA[echo hi]]>" in result.stdout


def test_json_print_emits_valid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.record,
        "build_record",
        lambda: {
            "version": 2,
            "scope": "command",
            "history_id": "abc",
            "command": "true",
            "result": {"status": 0},
            "output": {
                "state": "captured",
                "source": "atuin-pty-proxy",
                "text": "",
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
