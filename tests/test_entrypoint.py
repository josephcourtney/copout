"""Run the installed command with subprocesses at the external service boundaries."""

import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import pytest

ATUIN_SCRIPT = r"""
import json
import os
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("atuin 18.19.0")
elif args[:2] == ["config", "get"]:
    print("true")
elif args[:2] == ["history", "list"]:
    assert args[2:5] == ["--session", "--print0", "--reverse=false"]
    assert args[5] == "--format"
    assert os.environ["ATUIN_SESSION"] == "test-session"
    if os.environ.get("HISTORY_ERROR"):
        print("history unavailable", file=sys.stderr)
        sys.exit(2)
    if os.environ.get("MALFORMED_HISTORY"):
        print("invalid record", end="\0")
    else:
        for row in json.loads(os.environ["HISTORY_ROWS"]):
            print("\x1f".join(row), end="\0")
else:
    raise AssertionError(args)
"""

JERAKEEN_MODULE = """
import asyncio
import json
import os
from types import SimpleNamespace

class AtuinUnsupportedError(Exception):
    pass

class Client:
    description = "test daemon"

    @property
    def semantic(self):
        return self

    async def output(self, history_id):
        if os.environ.get("OUTPUT_STALL"):
            await asyncio.Event().wait()
        await asyncio.sleep(0)
        if os.environ.get("OUTPUT_UNSUPPORTED"):
            raise AtuinUnsupportedError("UNIMPLEMENTED")
        if os.environ.get("OUTPUT_ERROR"):
            raise RuntimeError("output unavailable")
        text = json.loads(os.environ["OUTPUTS"]).get(history_id)
        return None if text is None else SimpleNamespace(
            text=text, truncated=os.environ.get("TRUNCATED") == "1",
            observed_bytes=int(os.environ.get("OBSERVED_BYTES", len(text.encode()))),
            total_bytes=len(text.encode()))

    async def status(self):
        if os.environ.get("STATUS_STALL"):
            await asyncio.Event().wait()
        return SimpleNamespace(healthy=True, version="18.19.0", pid=123, protocol=1)

    async def __aenter__(self):
        if os.environ.get("DAEMON_ERROR"):
            raise RuntimeError("daemon unavailable")
        return self

    async def __aexit__(self, *args):
        pass

def connect(*, timeout):
    return Client()
"""


@dataclass
class CommandEnvironment:
    bin_dir: Path
    clipboard: Path
    env: dict[str, str]

    def run(self, *args: str, module: bool = False) -> subprocess.CompletedProcess[str]:
        launcher = Path(sysconfig.get_path("scripts")) / "copout"
        assert launcher.is_file(), "Install Copout before running command tests"
        command = [sys.executable, "-m", "copout.cli"] if module else [str(launcher)]
        return subprocess.run(
            [*command, *args],
            env=self.env,
            cwd=self.bin_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )


def executable(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)


@pytest.fixture
def command_env(tmp_path: Path) -> CommandEnvironment:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "jerakeen.py").write_text(JERAKEEN_MODULE)
    executable(bin_dir / "atuin", ATUIN_SCRIPT)
    clipboard = tmp_path / "clipboard.txt"
    executable(
        bin_dir / "pbcopy",
        "import os, sys\nfrom pathlib import Path\n"
        'Path(os.environ["CLIPBOARD_FILE"]).write_text(sys.stdin.read())\n'
        'sys.exit(int(os.environ.get("CLIPBOARD_STATUS", "0")))\n',
    )
    env = dict(os.environ)
    for key in (
        "HISTORY_ERROR",
        "MALFORMED_HISTORY",
        "OUTPUT_ERROR",
        "DAEMON_ERROR",
        "CLIPBOARD_STATUS",
        "TRUNCATED",
        "OBSERVED_BYTES",
        "OUTPUT_STALL",
        "OUTPUT_UNSUPPORTED",
        "STATUS_STALL",
    ):
        env.pop(key, None)
    env.update(
        PATH=str(bin_dir),
        PYTHONPATH=os.pathsep.join((str(tmp_path), str(Path(__file__).parents[1] / "src"))),
        ATUIN_SESSION="test-session",
        CLIPBOARD_FILE=str(clipboard),
        HISTORY_ROWS=json.dumps(
            [
                ["self", "2026-09-18 12:00:03", "/tmp", "0", "1ms", "copout -p"],
                ["new", "2026-09-18 12:00:02", "/tmp", "0", "71ms", "printf 'héllo\\n'"],
                ["failed", "2026-09-18 12:00:01", "/tmp", "2", "1s", "exit 2"],
                ["old", "2026-09-18 12:00:00", "/tmp", "0", "2ms", "true"],
            ]
        ),
        OUTPUTS=json.dumps({"new": "héllo\n", "failed": "failure\n", "old": ""}),
    )
    return CommandEnvironment(bin_dir, clipboard, env)


@pytest.mark.parametrize("module", [False, True])
def test_command_prints_captured_output(command_env: CommandEnvironment, module: bool) -> None:
    result = command_env.run("--print", "--json", module=module)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["history_id"] == "new"
    assert payload["output"]["text"] == "héllo\n"
    assert payload["output"]["state"] == "captured"
    assert payload["timing"]["duration"] == pytest.approx(0.071)
    assert not command_env.clipboard.exists()


def test_command_copies_to_helper(command_env: CommandEnvironment) -> None:
    result = command_env.run()
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    copied = command_env.clipboard.read_text()
    assert copied.startswith('<copout version="4"')
    assert "<![CDATA[héllo\n]]>" in copied


@pytest.mark.parametrize("failure", [False, True])
def test_command_selects_and_orders_history(command_env: CommandEnvironment, failure: bool) -> None:
    args = ["--print", "--json", "--last", "3"]
    if failure:
        args.append("--failure")
    result = command_env.run(*args)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [row["history_id"] for row in payload["runs"]] == (
        ["failed"] if failure else ["old", "failed", "new"]
    )
    if not failure:
        assert payload["runs"][0]["output"]["state"] == "captured"
        assert payload["runs"][0]["output"]["text"] == ""


@pytest.mark.parametrize("scenario", ["missing", "DAEMON_ERROR", "OUTPUT_ERROR"])
def test_command_preserves_history_without_output(
    command_env: CommandEnvironment, scenario: str
) -> None:
    if scenario == "missing":
        command_env.env["OUTPUTS"] = "{}"
    else:
        command_env.env[scenario] = "1"
    result = command_env.run("--print", "--json")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["history_id"] == "new"
    assert payload["output"]["state"] == "unavailable"


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("HISTORY_ERROR", "history unavailable"),
        ("MALFORMED_HISTORY", "unrecognized format"),
        ("empty", "no previous non-copout command"),
        ("session", "ATUIN_SESSION is not set"),
        ("atuin", "not on PATH"),
    ],
)
def test_command_reports_history_failures(
    command_env: CommandEnvironment, scenario: str, message: str
) -> None:
    if scenario == "empty":
        command_env.env["HISTORY_ROWS"] = "[]"
    elif scenario == "session":
        command_env.env.pop("ATUIN_SESSION")
    elif scenario == "atuin":
        (command_env.bin_dir / "atuin").unlink()
    else:
        command_env.env[scenario] = "1"
    result = command_env.run("--print")
    assert result.returncode == 3
    assert result.stdout == ""
    assert message in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("missing", [False, True])
def test_command_reports_clipboard_failure(command_env: CommandEnvironment, missing: bool) -> None:
    if missing:
        (command_env.bin_dir / "pbcopy").unlink()
    else:
        command_env.env["CLIPBOARD_STATUS"] = "7"
    result = command_env.run()
    assert result.returncode == (127 if missing else 7)
    assert "clipboard helper" in result.stderr


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_command_help_needs_no_services(command_env: CommandEnvironment, flag: str) -> None:
    command_env.env.pop("ATUIN_SESSION")
    (command_env.bin_dir / "atuin").unlink()
    result = command_env.run(flag)
    assert result.returncode == 0, result.stderr
    assert "--print" in result.stdout


@pytest.mark.parametrize("subcommand", ["doctor", "verify"])
@pytest.mark.parametrize("available", [False, True])
def test_command_diagnostics(
    command_env: CommandEnvironment, subcommand: str, available: bool
) -> None:
    if not available:
        command_env.env["DAEMON_ERROR"] = "1"
    result = command_env.run(subcommand)
    assert result.returncode == (0 if available else 5 if subcommand == "doctor" else 1)
    assert result.stderr == ""
    assert ("PASS" if available else "daemon") in result.stdout


@pytest.mark.parametrize("scenario", ["OUTPUT_STALL", "STATUS_STALL"])
def test_stalled_daemon_requests_terminate(command_env: CommandEnvironment, scenario: str) -> None:
    command_env.env[scenario] = "1"
    if scenario == "OUTPUT_STALL":
        result = command_env.run("--print", "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["output"]["state"] == "unavailable"
    else:
        result = command_env.run("doctor")
        assert result.returncode == 5
        assert "status request timed out" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("as_json", [False, True])
def test_truncated_output_metadata(command_env: CommandEnvironment, as_json: bool) -> None:
    command_env.env.update(TRUNCATED="1", OBSERVED_BYTES="10000")
    result = command_env.run("--print", *(["--json"] if as_json else []))
    assert result.returncode == 0, result.stderr
    if as_json:
        output = json.loads(result.stdout)["output"]
        assert output["truncated"] is True
        assert output["observed_bytes"] == 10000
        assert output["total_bytes"] == len("héllo\n".encode())
    else:
        output_element = ElementTree.fromstring(result.stdout).find("run/output")
        assert output_element is not None
        assert output_element.attrib["truncated"] == "true"
        assert output_element.attrib["observed_bytes"] == "10000"
        assert output_element.attrib["total_bytes"] == str(len("héllo\n".encode()))


def test_command_xml_round_trips_ansi_output(command_env: CommandEnvironment) -> None:
    original = "\x1b[31mred\x1b[0m\r\n"
    command_env.env["OUTPUTS"] = json.dumps({"new": original})
    result = command_env.run("--print")
    assert result.returncode == 0, result.stderr
    output = ElementTree.fromstring(result.stdout).find("run/output")
    assert output is not None
    assert output.attrib["encoding"] == "json-string"
    assert json.loads(output.text or "") == original


@pytest.mark.parametrize("subcommand", ["doctor", "verify", "print"])
def test_unsupported_output_rpc_is_reported(
    command_env: CommandEnvironment, subcommand: str
) -> None:
    command_env.env["OUTPUT_UNSUPPORTED"] = "1"
    args = ("--print", "--json") if subcommand == "print" else (subcommand,)
    result = command_env.run(*args)
    assert result.returncode == {"doctor": 5, "verify": 1, "print": 0}[subcommand]
    assert result.stderr == ""
    assert "UNIMPLEMENTED" in result.stdout
    assert "does not implement" in result.stdout
    if subcommand == "print":
        output = json.loads(result.stdout)["output"]
        assert output["state"] == "unavailable"
        assert "UNIMPLEMENTED" in output["error"]
