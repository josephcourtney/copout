from __future__ import annotations

import sys
from typing import Annotated

import typer

from . import atuin, clipboard, doctor, record, render, selection

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Copy recent structured terminal history from Atuin to the clipboard.",
    invoke_without_command=True,
    no_args_is_help=False,
    rich_markup_mode=None,
)


def _start_writer(*, print_output: bool) -> tuple[clipboard.ClipboardWriter | None, int | None]:
    if print_output:
        return None, None
    try:
        return clipboard.start_clipboard_writer(), None
    except clipboard.ClipboardStartError as exc:
        print(f"copout: {exc}", file=sys.stderr)
        return None, 127


def _write_record(
    captured: record.CopoutRecord,
    *,
    writer: clipboard.ClipboardWriter | None,
    as_json: bool,
) -> int:
    rendered = render.render(captured, as_json=as_json)
    if writer is None:
        sys.stdout.write(rendered)
        return 0
    return writer.write(rendered)


def _report_atuin_error(exc: record.AtuinError) -> int:
    print(f"copout: {exc}", file=sys.stderr)
    print("copout: run `copout doctor` for diagnostics", file=sys.stderr)
    return 3


def run(*, print_output: bool, as_json: bool, count: int, failure: bool) -> int:
    writer, error_code = _start_writer(print_output=print_output)
    if error_code is not None:
        return error_code

    try:
        try:
            captured = (
                record.build_record()
                if count == 1 and not failure
                else record.build_history(count=count, failed_only=failure)
            )
        except record.AtuinError as exc:
            return _report_atuin_error(exc)
        return _write_record(captured, writer=writer, as_json=as_json)
    finally:
        if writer is not None:
            writer.abort()


def run_pick(
    *,
    selectors: list[str],
    limit: int,
    print_output: bool,
    as_json: bool,
) -> int:
    try:
        candidates = atuin.recent_history(limit)
    except record.AtuinError as exc:
        return _report_atuin_error(exc)

    try:
        requested = selectors or selection.prompt_selection(candidates)
        selected = selection.select_entries(candidates, requested)
    except selection.SelectionError as exc:
        print(f"copout: {exc}", file=sys.stderr)
        return 2

    writer, error_code = _start_writer(print_output=print_output)
    if error_code is not None:
        return error_code

    try:
        hydrated = atuin.hydrate_outputs(selected)
        captured = record.build_history_from_entries(hydrated)
        return _write_record(captured, writer=writer, as_json=as_json)
    finally:
        if writer is not None:
            writer.abort()


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


@app.command("pick")
def pick_command(
    selectors: Annotated[
        list[str] | None,
        typer.Argument(help="Recent command numbers or ranges, for example: 1 3 5-7."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", min=1, help="Number of recent commands available to pick."),
    ] = selection.DEFAULT_PICK_LIMIT,
    print_output: Annotated[
        bool, typer.Option("--print", "-p", help="Print instead of copying.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of XML.")] = False,
) -> None:
    """Choose arbitrary recent commands and copy them as one history record."""
    raise typer.Exit(
        run_pick(
            selectors=selectors or [],
            limit=limit,
            print_output=print_output,
            as_json=as_json,
        )
    )


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
