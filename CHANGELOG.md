# Changelog

## Unreleased

### Changed

- Advance structured output to schema version 8 with one universal capture envelope: every result contains a non-empty `runs` array, including single-command captures.
- Remove the schema-v7 `scope` distinction and `history` summary object; query syntax no longer changes the record shape.
- Apply presentation output budgets uniformly to one-run and multi-run captures, and always include each run's Atuin `history_id` in XML.
- Make the interactive picker the default when `copout` is invoked without an explicit selection query; formatting and context options can be supplied before opening the picker.
- When the interactive picker has no selected entries, pressing Enter now captures the most recent eligible command (history position `1`) instead of requiring an explicit selection.
- Accept history selectors directly at the root, so `copout 1`, `copout 1 3`, `copout 2-5`, and comma-separated combinations gather exactly those entries without opening the TUI. Explicit selectors automatically extend history discovery far enough to resolve the oldest requested position instead of being limited by the TUI browse window.
- Add root-level `--preselect` for relative history positions and move `--preselect-records` to the root interface as well; both open the TUI and may be combined, while `copout pick` remains as a compatibility spelling.
- Expose the TUI browse `--limit` at the root now that bare `copout` opens the picker.
- Add Vim-style picker navigation: `j`/`k`, `g`/`G`, and `Ctrl-D`/`Ctrl-U`, while retaining the existing arrow, Home/End, and Page Up/Page Down controls.
- Extend stable record-ID preselection contiguously through the oldest required entry so picker numbering remains the true relative history position even beyond the normal browse limit.
- Bound concurrent Atuin output hydration requests to avoid large explicit selections producing unbounded daemon RPC bursts.

### Fixed

- Report an error instead of emitting a successful empty history record when `--failure` or another history-count query has no matching commands.
- Filter Copout's supported module and wrapper invocation forms (`python -m copout.cli`, `uv run python -m copout.cli`, `uvx copout`, and `command copout`) out of candidate history as well as direct `copout` invocations.
- Add regression coverage for config-path precedence and CLI overrides over configured context settings.

## 0.10.0 - 2026-10-01

### Added

- Add `--markdown` output for commands and picked history, with safe fences and capture notes.
- Add `copout pick` for arbitrary recent-command selection. Selectors are 1-based newest-first offsets and support inclusive ranges such as `2-4`; selected runs are emitted chronologically.
- Replace the line-oriented interactive picker with a bounded Textual inline checklist: navigate a scrollable history, toggle commands with Space, confirm the accumulated selection with Enter, and cancel with Esc or `q` without touching the clipboard.
- Increase the default interactive candidate window from 20 to 100 commands now that candidates scroll within a fixed-height picker.
- Add `copout pick --preselect-records id1,id2,...` so external/runbook integrations can open the normal picker with exact Atuin record IDs already selected. Required IDs can extend the candidate window beyond `--limit`, and unknown IDs fail explicitly rather than falling back to command-text matching.
- Add `--pretty-attributes` as an opt-in XML layout mode; compact attributes remain the default.
- Add configurable execution-context capture and advance the structured-output schema to version 7. Default context includes capture/record timestamps, Git root/branch/commit/detached/dirty state, login shell, OS family/architecture, Atuin session ID, and Python environment details when available.
- Add privacy-sensitive context as explicit opt-ins: hostname, shell/OS versions, extended Git state, bounded Git diff, selected environment variables, and executable resolution.
- Add persistent context configuration through `$COPOUT_CONFIG`, `$XDG_CONFIG_HOME/copout/config.toml`, or `~/.config/copout/config.toml`, with CLI values overriding file settings.
- Mark Git metadata as capture-time observation so current repository state is not presented as historical command state.
- Add `just fix`, `just repair`, mutating `just lint`/`just format`, optional `--unsafe-fixes`, and a non-mutating `just check` validation path.

### Output and daemon reliability

- Upgrade to Jerakeen 0.10.0 and Atuin daemon protocol 3; captured output is retrieved through `History.GetCommandOutput` rather than the removed Semantic service.
- Report unsupported output RPCs and other retrieval errors instead of treating every failure as a missing capture.
- Read CLI history before opening daemon clients during diagnostics, avoiding subprocess forks after gRPC initialization.
- Start clipboard helpers before Jerakeen/gRPC access so normal clipboard delivery does not fork a new process after gRPC initialization; abort prestarted helpers without publishing an empty clipboard on retrieval failure.
- Keep Textual off the normal startup path; it is imported only for interactive `copout pick`.
- Fetch daemon output only for commands selected by `copout pick`, rather than hydrating the entire candidate window.
- Replace the manual/opt-in live-shell probe with a self-contained PTY-driven test that starts an interactive zsh, exercises the real Atuin integration, drains terminal output safely, and verifies captured probe output.
- Advance output schema to version 6 before version 7: remove the redundant root `selected` attribute, replace human-formatted duration strings with integer `duration_ms`, rename normalized byte counts to `captured_bytes`, formalize the XML text/`json-string` encoding contract, and expose sparse extended capture metadata only when needed.
- Support sparse `state`, `encoding`, `truncated`, `captured_bytes`, `observed_bytes`, `total_bytes`, and upstream `exit_capture_complete` output metadata while keeping ordinary complete `<output>` elements attribute-free.
- Reserve schema `total_bytes` for a true complete-output size; Atuin's stored-rendered-output byte count is intentionally not mapped to that field.
- Bound presented output for multi-run history records to 128 KiB per run and 512 KiB overall, preserving useful head and tail context with an explicit omission marker. Bare single-command output remains unbounded by Copout.
- Preserve XML-invalid text reversibly with explicit JSON-string markers and retain daemon truncation and byte-count metadata in the internal/JSON record.
- Bound daemon output and status requests to three seconds; retain history when output requests time out.
- Cache capture-time Git inspection by working directory during multi-run assembly to avoid redundant subprocess work.

### Changed

- Replace Atuin MCP access with Atuin's documented history CLI for persisted session history and Jerakeen for direct daemon output access.
- Remove `copout install`; Copout no longer writes shell startup files or Atuin configuration.
- Make `copout doctor` read-only and have it report exact Atuin remediation commands; `copout verify` is a concise end-to-end assertion.
- Remove production dependency-injection/factory plumbing that existed only for tests.
- Add typed command/history record schemas and remove defensive renderer shape recovery.
- Simplify structured output schema to version 3 earlier in the development cycle: redundant `capture` metadata was removed, with provenance represented by top-level `source` and per-run output `source`.
- Remove the Kitty watcher, Copout state directory, background writer, pending markers, command journal, retention logic, and watcher installation lifecycle.
- Align policy and contributor documentation around a strictly read-only product boundary: context enrichment may inspect current state but may not modify repositories, shell startup files, Atuin configuration, or external tool configuration.

### Fixed

- Handle clipboard text encoding failures with a diagnostic and exit status.
- Bound daemon error details in output records and recognize `uv run copout` in history filtering.
- Restore the documented copy/print CLI and synchronous console entry point, removing the experimental future-history tail path.
- Align package-version handling with project metadata and repair stale test assumptions.
- Make live PTY tests independent of prompt themes and prevent PTY-buffer deadlocks by continuously draining child-terminal output.
- Tolerate terminal prompt decoration that Atuin may append to otherwise correct captured probe output.
- Exercise the installed command with controlled service and clipboard processes, and isolate subprocess tests from the user's real Copout configuration.
- Add XML round-trip, normalized-output, truncation, stalled-service, multi-command selection, output-budget, inline-picker, sparse-metadata, XML-layout, context-configuration, and live-shell regression tests.

## 0.7.4 - 2026-08-19

- Parse Atuin 18.19 MCP history's documented Markdown text response instead of assuming JSON structured content.
- Extract terminal output from the `Selected output` section and remove Atuin line-number prefixes.
- Distinguish missing `ATUIN_SESSION` from an actual empty session in `copout doctor`.

## 0.7.3 - 2026-08-19

### Fixed

- Narrow structured renderer sections before access so `ty` can prove they are mappings/lists.
- Accept structural MCP client factories, allowing typed test doubles without coupling them to the concrete client class.

## 0.7.2

- Fix Atuin MCP history retrieval by omitting optional empty search queries.
- Continue adapting history filter arguments to the live Atuin MCP schema.
