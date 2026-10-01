from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from . import atuin, clipboard, doctor, record, render, selection
from .config import ConfigError, ContextOptions, load_context_options

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
    as_markdown: bool,
    pretty_attributes: bool,
) -> int:
    rendered = render.render(
        captured,
        as_json=as_json,
        as_markdown=as_markdown,
        pretty_attributes=pretty_attributes,
    )
    if writer is None:
        sys.stdout.write(rendered)
        return 0
    return writer.write(rendered)


def _report_atuin_error(exc: record.AtuinError) -> int:
    print(f"copout: {exc}", file=sys.stderr)
    print("copout: run `copout doctor` for diagnostics", file=sys.stderr)
    return 3


def _context_options(
    *,
    config_path: Path | None,
    context_enabled: bool | None,
    git_context: bool | None,
    git_extended: bool | None,
    git_diff: bool | None,
    system_context: bool | None,
    hostname_context: bool | None,
    shell_version: bool | None,
    os_version: bool | None,
    python_context: bool | None,
    env_vars: list[str],
    executables: list[str],
) -> ContextOptions:
    try:
        options = load_context_options(config_path)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc), param_hint="--config") from exc

    overrides: dict[str, bool | None] = {
        "enabled": context_enabled,
        "git": git_context,
        "git_extended": git_extended,
        "git_diff": git_diff,
        "hostname": hostname_context,
        "shell_version": shell_version,
        "os_version": os_version,
        "python": python_context,
    }
    if system_context is not None:
        overrides.update(
            shell=system_context,
            platform=system_context,
            session=system_context,
        )
    options = options.with_overrides(**overrides)

    if env_vars:
        options = options.with_overrides(env=tuple(dict.fromkeys((*options.env, *env_vars))))
    if executables:
        options = options.with_overrides(
            executables=tuple(dict.fromkeys((*options.executables, *executables)))
        )
    return options


def run(
    *,
    print_output: bool,
    as_json: bool,
    as_markdown: bool,
    pretty_attributes: bool,
    count: int,
    failure: bool,
    context_options: ContextOptions | None = None,
) -> int:
    writer, error_code = _start_writer(print_output=print_output)
    if error_code is not None:
        return error_code

    try:
        try:
            captured = (
                record.build_record(context_options=context_options)
                if count == 1 and not failure
                else record.build_history(
                    count=count,
                    failed_only=failure,
                    context_options=context_options,
                )
            )
        except record.AtuinError as exc:
            return _report_atuin_error(exc)
        return _write_record(
            captured,
            writer=writer,
            as_json=as_json,
            as_markdown=as_markdown,
            pretty_attributes=pretty_attributes,
        )
    finally:
        if writer is not None:
            writer.abort()


def _pick_entries(
    candidates: list[atuin.HistoryEntry],
    *,
    preselected_ids: list[str] | None = None,
) -> list[atuin.HistoryEntry] | None:
    from . import picker  # noqa: PLC0415

    return picker.pick_entries(candidates, preselected_ids=preselected_ids or ())


def run_pick(
    *,
    selectors: list[str],
    preselect_records: list[str],
    limit: int,
    print_output: bool,
    as_json: bool,
    as_markdown: bool,
    pretty_attributes: bool,
    context_options: ContextOptions | None = None,
) -> int:
    try:
        record_ids = selection.parse_record_ids(preselect_records) if preselect_records else []
        if selectors and record_ids:
            raise selection.SelectionError(
                "command selectors and --preselect-records cannot be combined"
            )
        candidates = (
            atuin.recent_history(limit, required_ids=record_ids)
            if record_ids
            else atuin.recent_history(limit)
        )
    except selection.SelectionError as exc:
        print(f"copout: {exc}", file=sys.stderr)
        return 2
    except record.AtuinError as exc:
        return _report_atuin_error(exc)

    try:
        if selectors:
            selected = selection.select_entries(candidates, selectors)
        else:
            if record_ids:
                selection.select_entries_by_ids(candidates, record_ids)
            selected = _pick_entries(candidates, preselected_ids=record_ids)
            if selected is None:
                return 0
    except selection.SelectionError as exc:
        print(f"copout: {exc}", file=sys.stderr)
        return 2

    writer, error_code = _start_writer(print_output=print_output)
    if error_code is not None:
        return error_code

    try:
        hydrated = atuin.hydrate_outputs(selected)
        captured = record.build_history_from_entries(
            hydrated,
            context_options=context_options,
        )
        return _write_record(
            captured,
            writer=writer,
            as_json=as_json,
            as_markdown=as_markdown,
            pretty_attributes=pretty_attributes,
        )
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
    as_markdown: Annotated[
        bool, typer.Option("--markdown", help="Emit readable Markdown instead of XML.")
    ] = False,
    pretty_attributes: Annotated[
        bool,
        typer.Option(
            "--pretty-attributes",
            help="Put XML attributes on separate lines when an element has several.",
        ),
    ] = False,
    last: Annotated[
        int, typer.Option("--last", "-n", min=1, help="Include the last N commands.")
    ] = 1,
    failure: Annotated[
        bool,
        typer.Option("--failure", help="Select the most recent failed command."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Read context settings from this TOML file."),
    ] = None,
    context_enabled: Annotated[
        bool | None,
        typer.Option("--context/--no-context", help="Enable or disable all extra context."),
    ] = None,
    git_context: Annotated[
        bool | None,
        typer.Option("--git-context/--no-git-context", help="Include current Git state for each cwd."),
    ] = None,
    git_extended: Annotated[
        bool | None,
        typer.Option("--git-extended/--no-git-extended", help="Include upstream, divergence, remote, and changed files."),
    ] = None,
    git_diff: Annotated[
        bool | None,
        typer.Option("--git-diff/--no-git-diff", help="Include a bounded working-tree Git diff."),
    ] = None,
    system_context: Annotated[
        bool | None,
        typer.Option("--system-context/--no-system-context", help="Include shell, platform, architecture, and Atuin session."),
    ] = None,
    hostname_context: Annotated[
        bool | None,
        typer.Option("--hostname-context/--no-hostname-context", help="Include the hostname."),
    ] = None,
    shell_version: Annotated[
        bool | None,
        typer.Option("--shell-version/--no-shell-version", help="Include the login-shell version."),
    ] = None,
    os_version: Annotated[
        bool | None,
        typer.Option("--os-version/--no-os-version", help="Include the OS release/version."),
    ] = None,
    python_context: Annotated[
        bool | None,
        typer.Option("--python-context/--no-python-context", help="Include Python interpreter/environment details."),
    ] = None,
    env_vars: Annotated[
        list[str] | None,
        typer.Option("--env", help="Include this environment variable; repeat as needed."),
    ] = None,
    executables: Annotated[
        list[str] | None,
        typer.Option("--resolve", help="Include the resolved path of this executable; repeat as needed."),
    ] = None,
) -> None:
    """Copy recent Atuin command history and captured output."""
    if ctx.invoked_subcommand is not None:
        return
    if as_json and as_markdown:
        raise typer.BadParameter("--json and --markdown cannot be combined")
    options = _context_options(
        config_path=config_path,
        context_enabled=context_enabled,
        git_context=git_context,
        git_extended=git_extended,
        git_diff=git_diff,
        system_context=system_context,
        hostname_context=hostname_context,
        shell_version=shell_version,
        os_version=os_version,
        python_context=python_context,
        env_vars=env_vars or [],
        executables=executables or [],
    )
    raise typer.Exit(
        run(
            print_output=print_output,
            as_json=as_json,
            as_markdown=as_markdown,
            pretty_attributes=pretty_attributes,
            count=last,
            failure=failure,
            context_options=options,
        )
    )


@app.command("pick")
def pick_command(
    selectors: Annotated[
        list[str] | None,
        typer.Argument(help="Recent command numbers or ranges, for example: 1 3 5-7."),
    ] = None,
    preselect_records: Annotated[
        list[str] | None,
        typer.Option(
            "--preselect-records",
            help="Open the picker with these Atuin record IDs selected; values may be comma-separated.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", min=1, help="Number of recent commands available to pick."),
    ] = selection.DEFAULT_PICK_LIMIT,
    print_output: Annotated[
        bool, typer.Option("--print", "-p", help="Print instead of copying.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of XML.")] = False,
    as_markdown: Annotated[
        bool, typer.Option("--markdown", help="Emit readable Markdown instead of XML.")
    ] = False,
    pretty_attributes: Annotated[
        bool,
        typer.Option(
            "--pretty-attributes",
            help="Put XML attributes on separate lines when an element has several.",
        ),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Read context settings from this TOML file."),
    ] = None,
    context_enabled: Annotated[
        bool | None,
        typer.Option("--context/--no-context", help="Enable or disable all extra context."),
    ] = None,
    git_context: Annotated[
        bool | None,
        typer.Option("--git-context/--no-git-context", help="Include current Git state for each cwd."),
    ] = None,
    git_extended: Annotated[
        bool | None,
        typer.Option("--git-extended/--no-git-extended", help="Include upstream, divergence, remote, and changed files."),
    ] = None,
    git_diff: Annotated[
        bool | None,
        typer.Option("--git-diff/--no-git-diff", help="Include a bounded working-tree Git diff."),
    ] = None,
    system_context: Annotated[
        bool | None,
        typer.Option("--system-context/--no-system-context", help="Include shell, platform, architecture, and Atuin session."),
    ] = None,
    hostname_context: Annotated[
        bool | None,
        typer.Option("--hostname-context/--no-hostname-context", help="Include the hostname."),
    ] = None,
    shell_version: Annotated[
        bool | None,
        typer.Option("--shell-version/--no-shell-version", help="Include the login-shell version."),
    ] = None,
    os_version: Annotated[
        bool | None,
        typer.Option("--os-version/--no-os-version", help="Include the OS release/version."),
    ] = None,
    python_context: Annotated[
        bool | None,
        typer.Option("--python-context/--no-python-context", help="Include Python interpreter/environment details."),
    ] = None,
    env_vars: Annotated[
        list[str] | None,
        typer.Option("--env", help="Include this environment variable; repeat as needed."),
    ] = None,
    executables: Annotated[
        list[str] | None,
        typer.Option("--resolve", help="Include the resolved path of this executable; repeat as needed."),
    ] = None,
) -> None:
    """Choose arbitrary recent commands and copy them as one history record."""
    if as_json and as_markdown:
        raise typer.BadParameter("--json and --markdown cannot be combined")
    options = _context_options(
        config_path=config_path,
        context_enabled=context_enabled,
        git_context=git_context,
        git_extended=git_extended,
        git_diff=git_diff,
        system_context=system_context,
        hostname_context=hostname_context,
        shell_version=shell_version,
        os_version=os_version,
        python_context=python_context,
        env_vars=env_vars or [],
        executables=executables or [],
    )
    raise typer.Exit(
        run_pick(
            selectors=selectors or [],
            preselect_records=preselect_records or [],
            limit=limit,
            print_output=print_output,
            as_json=as_json,
            as_markdown=as_markdown,
            pretty_attributes=pretty_attributes,
            context_options=options,
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
