from __future__ import annotations

from copout import doctor
from copout.atuin import AtuinError, DaemonInfo, HistoryEntry


def test_doctor_reports_missing_atuin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda executable: None)

    assert doctor.doctor() == 2
    assert "Atuin is a required dependency" in capsys.readouterr().out


def test_doctor_passes_with_history_and_jerakeen_output(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ATUIN_SESSION", "session")
    monkeypatch.setattr(doctor.shutil, "which", lambda executable: "/usr/bin/atuin")
    monkeypatch.setattr(doctor, "_command", lambda args: (0, "atuin 18.19.0"))
    monkeypatch.setattr(
        doctor,
        "daemon_info",
        lambda: DaemonInfo("/tmp/atuin.sock", True, "18.19.0", 123, 1),
    )
    monkeypatch.setattr(
        doctor,
        "recent_entries",
        lambda count, include_output: [
            HistoryEntry("id", "false", "/tmp", 1, 0.01, "2026-08-19 10:00:00", "")
        ],
    )

    assert doctor.doctor() == 0
    output = capsys.readouterr().out
    assert "jerakeen daemon:  yes" in output
    assert "PASS: Atuin history and Jerakeen daemon output" in output


def test_doctor_treats_daemon_failure_as_partial(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ATUIN_SESSION", "session")
    monkeypatch.setattr(doctor.shutil, "which", lambda executable: "/usr/bin/atuin")
    monkeypatch.setattr(doctor, "_command", lambda args: (0, "atuin 18.19.0"))

    def no_daemon() -> DaemonInfo:
        raise AtuinError("no daemon socket")

    monkeypatch.setattr(doctor, "daemon_info", no_daemon)
    monkeypatch.setattr(
        doctor,
        "recent_entries",
        lambda count, include_output: [HistoryEntry("id", "echo hi", output=None)],
    )

    assert doctor.doctor() == 5
    output = capsys.readouterr().out
    assert "jerakeen daemon:  NO" in output
    assert "PARTIAL: Atuin history works" in output
