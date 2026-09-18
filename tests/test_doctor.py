from __future__ import annotations

from copout import doctor
from copout.atuin import DaemonInfo, HistoryEntry

DEFAULT_DAEMON = DaemonInfo("/tmp/atuin.sock", True, "18.19.0", 123, 1)
DEFAULT_LATEST = HistoryEntry("id", "false", "/tmp", 1, 0.01, "", "captured\n")


def diagnostic(
    *,
    atuin_path: str | None = "/usr/bin/atuin",
    atuin_version: str | None = "atuin 18.19.0",
    session_present: bool = True,
    daemon_enabled: bool | None = True,
    daemon_autostart: bool | None = True,
    pty_proxy_enabled: bool | None = True,
    daemon: DaemonInfo | None = DEFAULT_DAEMON,
    daemon_error: str | None = None,
    latest: HistoryEntry | None = DEFAULT_LATEST,
    history_error: str | None = None,
) -> doctor.Diagnostic:
    return doctor.Diagnostic(
        atuin_path=atuin_path,
        atuin_version=atuin_version,
        session_present=session_present,
        daemon_enabled=daemon_enabled,
        daemon_autostart=daemon_autostart,
        pty_proxy_enabled=pty_proxy_enabled,
        daemon=daemon,
        daemon_error=daemon_error,
        latest=latest,
        history_error=history_error,
    )


def test_doctor_reports_missing_atuin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor, "inspect", lambda: diagnostic(atuin_path=None, atuin_version=None))

    assert doctor.doctor() == 2
    assert "Atuin is a required dependency" in capsys.readouterr().out


def test_doctor_passes_with_history_and_jerakeen_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor, "inspect", diagnostic)

    assert doctor.doctor() == 0
    output = capsys.readouterr().out
    assert "jerakeen daemon:   yes" in output
    assert "PASS: Atuin history and Jerakeen daemon output" in output


def test_doctor_reports_configuration_remediation(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        doctor,
        "inspect",
        lambda: diagnostic(daemon_enabled=False, pty_proxy_enabled=False),
    )

    assert doctor.doctor() == 5
    output = capsys.readouterr().out
    assert "command-output capture is not fully configured" in output
    assert "atuin config set daemon.enabled true" in output
    assert "atuin config set pty_proxy.enabled true" in output
    assert "daemon.autostart" not in output.split("remediation:", 1)[1]


def test_doctor_treats_daemon_failure_as_partial(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        doctor,
        "inspect",
        lambda: diagnostic(
            daemon=None,
            daemon_error="no daemon socket",
            latest=HistoryEntry("id", "echo hi"),
        ),
    )

    assert doctor.doctor() == 5
    output = capsys.readouterr().out
    assert "jerakeen daemon:   NO" in output
    assert "configured for daemon operation" in output


def test_verify_is_concise_pass_fail(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor, "inspect", diagnostic)
    assert doctor.verify() == 0
    assert capsys.readouterr().out == "copout verify: PASS\n"

    monkeypatch.setattr(
        doctor,
        "inspect",
        lambda: diagnostic(latest=HistoryEntry("id", "false", output=None)),
    )
    assert doctor.verify() == 1
    assert "command output was not captured" in capsys.readouterr().out


def test_inspect_reads_history_before_starting_daemon_client(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("ATUIN_SESSION", "session")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/atuin")
    monkeypatch.setattr(doctor, "_command", lambda args: (0, "true"))

    def history(count: int) -> list[HistoryEntry]:
        calls.append("history")
        return [DEFAULT_LATEST]

    def daemon() -> DaemonInfo:
        calls.append("daemon")
        return DEFAULT_DAEMON

    monkeypatch.setattr(doctor, "recent_entries", history)
    monkeypatch.setattr(doctor, "daemon_info", daemon)
    assert doctor.inspect().latest == DEFAULT_LATEST
    assert calls == ["history", "daemon"]
