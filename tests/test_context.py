from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from copout import context, record, render
from copout.atuin import HistoryEntry
from copout.config import ContextOptions, load_context_options


def test_context_defaults_are_useful_but_privacy_conservative() -> None:
    options = ContextOptions()

    assert options.enabled is True
    assert options.git is True
    assert options.shell is True
    assert options.platform is True
    assert options.session is True
    assert options.python is True
    assert options.hostname is False
    assert options.git_extended is False
    assert options.git_diff is False
    assert options.env == ()
    assert options.executables == ()


def test_context_config_file_overrides_defaults(tmp_path: Path) -> None:
    path = tmp_path / "copout.toml"
    path.write_text(
        """
[context]
git = false
git_extended = true
hostname = true
shell_version = true
env = ["TERM", "LANG"]
executables = ["git", "python"]
""".strip()
    )

    options = load_context_options(path)

    assert options.git is False
    assert options.git_extended is True
    assert options.hostname is True
    assert options.shell_version is True
    assert options.env == ("TERM", "LANG")
    assert options.executables == ("git", "python")


def test_git_context_marks_state_as_observed_at_capture(monkeypatch) -> None:
    responses = {
        ("rev-parse", "--show-toplevel"): "/repo",
        ("rev-parse", "HEAD"): "abc123",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "feature",
        ("status", "--porcelain=v1", "--untracked-files=normal"): " M src/x.py",
    }

    monkeypatch.setattr(
        context,
        "_git",
        lambda args, *, cwd: responses.get(tuple(args)),
    )

    captured = context.capture_git_context("/repo/subdir", ContextOptions())

    assert captured == {
        "observed_at_capture": True,
        "root": "/repo",
        "commit": "abc123",
        "branch": "feature",
        "detached": False,
        "dirty": True,
    }


def test_xml_renders_environment_and_git_context() -> None:
    captured = record.build_history_from_entries([HistoryEntry("1", "git status", "/repo")])
    captured["environment"] = {
        "login_shell": "/bin/zsh",
        "os": "darwin",
        "arch": "arm64",
        "python": {
            "executable": "/repo/.venv/bin/python",
            "version": "3.14.0",
            "implementation": "cpython",
            "environment": "/repo/.venv",
        },
        "env": {"TERM": "xterm-kitty"},
        "executables": {"git": "/usr/bin/git"},
    }
    captured["runs"][0]["context"]["git"] = {
        "observed_at_capture": True,
        "root": "/repo",
        "branch": "main",
        "commit": "abc123",
        "dirty": True,
        "changed_files": ["src/x.py"],
        "diff": "diff --git a/src/x.py b/src/x.py",
        "diff_truncated": False,
    }

    root = ElementTree.fromstring(render.render(captured))

    environment = root.find("environment")
    assert environment is not None
    assert environment.attrib["login_shell"] == "/bin/zsh"
    assert environment.attrib["os"] == "darwin"
    assert environment.find("python") is not None
    variable = environment.find("variable")
    assert variable is not None and variable.attrib == {"name": "TERM", "value": "xterm-kitty"}

    git = root.find("run/git")
    assert git is not None
    assert git.attrib["observed_at_capture"] == "true"
    assert git.attrib["branch"] == "main"
    assert git.attrib["dirty"] == "true"
    assert git.findtext("changed-file") == "src/x.py"
    assert git.findtext("diff") == "diff --git a/src/x.py b/src/x.py"
