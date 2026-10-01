from __future__ import annotations

import os
import platform as platform_module
import shutil
import socket
import subprocess
import sys
from typing import TypedDict

from .config import ContextOptions

_GIT_TIMEOUT = 1.0
_DIFF_LIMIT = 64 * 1024


class GitContext(TypedDict, total=False):
    observed_at_capture: bool
    root: str
    branch: str
    detached: bool
    commit: str
    dirty: bool
    upstream: str
    ahead: int
    behind: int
    remote_url: str
    changed_files: list[str]
    diff: str
    diff_truncated: bool


class PythonContext(TypedDict, total=False):
    executable: str
    version: str
    implementation: str
    environment: str


class EnvironmentContext(TypedDict, total=False):
    login_shell: str
    shell_version: str
    os: str
    os_version: str
    arch: str
    hostname: str
    session_id: str
    python: PythonContext
    env: dict[str, str]
    executables: dict[str, str]


def _run(args: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git(args: list[str], *, cwd: str) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    result = _run([git, *args], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _changed_files(cwd: str) -> list[str]:
    status = _git(["status", "--porcelain=v1", "--untracked-files=normal"], cwd=cwd)
    if not status:
        return []
    paths: list[str] = []
    for line in status.splitlines():
        path = line[3:] if len(line) >= 4 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.append(path)
    return paths


def capture_git_context(cwd: str, options: ContextOptions) -> GitContext | None:
    if not options.enabled or not options.git or not cwd:
        return None
    root = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if root is None:
        return None

    result: GitContext = {"observed_at_capture": True, "root": root}
    commit = _git(["rev-parse", "HEAD"], cwd=cwd)
    if commit:
        result["commit"] = commit

    branch = _git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=cwd)
    if branch:
        result["branch"] = branch
        result["detached"] = False
    else:
        result["detached"] = True

    status = _git(["status", "--porcelain=v1", "--untracked-files=normal"], cwd=cwd)
    if status is not None:
        result["dirty"] = bool(status)

    if options.git_extended:
        upstream = _git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=cwd
        )
        if upstream:
            result["upstream"] = upstream
            counts = _git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], cwd=cwd)
            if counts:
                try:
                    ahead_text, behind_text = counts.split()
                    result["ahead"] = int(ahead_text)
                    result["behind"] = int(behind_text)
                except ValueError:
                    pass

            remote = upstream.split("/", 1)[0]
            remote_url = _git(["remote", "get-url", remote], cwd=cwd)
        else:
            remote_url = _git(["remote", "get-url", "origin"], cwd=cwd)
        if remote_url:
            result["remote_url"] = remote_url
        result["changed_files"] = _changed_files(cwd)

    if options.git_diff:
        diff = _git(["diff", "--no-ext-diff", "--binary", "HEAD"], cwd=cwd)
        if diff is not None:
            encoded = diff.encode()
            if len(encoded) > _DIFF_LIMIT:
                result["diff"] = encoded[:_DIFF_LIMIT].decode("utf-8", errors="ignore")
                result["diff_truncated"] = True
            else:
                result["diff"] = diff
                result["diff_truncated"] = False

    return result


def _shell_version(shell: str) -> str | None:
    result = _run([shell, "--version"])
    if result is None or result.returncode != 0:
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def capture_environment(options: ContextOptions) -> EnvironmentContext:
    if not options.enabled:
        return {}

    environment: EnvironmentContext = {}
    shell = os.environ.get("SHELL")
    if options.shell and shell:
        environment["login_shell"] = shell
        if options.shell_version and (version := _shell_version(shell)):
            environment["shell_version"] = version

    if options.platform:
        environment["os"] = platform_module.system().lower()
        environment["arch"] = platform_module.machine()
        if options.os_version:
            environment["os_version"] = platform_module.release()

    if options.hostname:
        environment["hostname"] = socket.gethostname()

    if options.session and (session := os.environ.get("ATUIN_SESSION")):
        environment["session_id"] = session

    if options.python:
        python_context: PythonContext = {
            "executable": sys.executable,
            "version": platform_module.python_version(),
            "implementation": platform_module.python_implementation().lower(),
        }
        if virtual_env := os.environ.get("VIRTUAL_ENV"):
            python_context["environment"] = virtual_env
        elif sys.prefix != getattr(sys, "base_prefix", sys.prefix):
            python_context["environment"] = sys.prefix
        environment["python"] = python_context

    requested_env = {
        name: value for name in options.env if (value := os.environ.get(name)) is not None
    }
    if requested_env:
        environment["env"] = requested_env

    resolved = {
        name: path for name in options.executables if (path := shutil.which(name)) is not None
    }
    if resolved:
        environment["executables"] = resolved

    return environment
