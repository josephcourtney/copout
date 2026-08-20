from __future__ import annotations

import sys
from typing import Annotated

import typer

from . import clipboard, doctor, record, render

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Copy recent structured terminal history from Atuin to the clipboard.",
    invoke_without_command=True,
    no_args_is_help=False,
    rich_markup_mode=None,
)


def run(*, print_output: bool, as_json: bool, count: int, failure: bool) -> int:
    try:
        captured = (
            record.build_record()
            if count == 1 and not failure
            else record.build_history(count=count, failed_only=failure)
        )
    except record.AtuinError as exc:
        print(f"copout: {exc}", file=sys.stderr)
        print("copout: run `copout doctor` for diagnostics", file=sys.stderr)
        return 3
    rendered = render.render(captured, as_json=as_json)
    if print_output:
        sys.stdout.write(rendered)
        return 0
    return clipboard.copy_to_clipboard(rendered)


@app.callback()
def cli(
    ctx: typer.Context,
    print_output: Annotated[
        bool, typer.Option("--print", "-p", help="Print instead of copying.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of XML.")] = False,
    last: Annotated[
        int, typer.Option("--last", "-n", min=1, help="Include the last N commands.")
    ] = 1,
    failure: Annotated[
        bool,
        typer.Option("--failure", help="Select the most recent failed command."),
    ] = False,
) -> None:
    """Copy recent Atuin command history and captured output."""
    if ctx.invoked_subcommand is not None:
        return
    raise typer.Exit(run(print_output=print_output, as_json=as_json, count=last, failure=failure))


@app.command("doctor")
def doctor_command() -> None:
    """Diagnose Atuin history and Jerakeen daemon integration."""
    raise typer.Exit(doctor.doctor())


@app.command("verify")
def verify_command() -> None:
    """Verify that Atuin history and Jerakeen command-output capture work."""
    raise typer.Exit(doctor.verify())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
