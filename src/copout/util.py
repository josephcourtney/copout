import subprocess
from dataclasses import dataclass

from .errors import AtuinError


@dataclass(frozen=True, slots=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str


def _run(args: list[str], *, timeout: float = 3) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AtuinError(str(exc)) from exc

    return CommandResult(
        code=result.returncode,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )
