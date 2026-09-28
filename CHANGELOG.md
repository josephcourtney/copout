# Changelog

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

## Unreleased

### Added

- Add `copout pick` for arbitrary recent-command selection. Selectors are 1-based newest-first offsets and support inclusive ranges such as `2-4`; selected runs are emitted chronologically.
- Replace the line-oriented interactive picker with a bounded Textual inline checklist: navigate a scrollable history, toggle commands with Space, confirm the accumulated selection with Enter, and cancel with Esc or `q` without touching the clipboard.
- Increase the default interactive candidate window from 20 to 100 commands now that candidates scroll within a fixed-height picker.
- Keep Textual off the normal startup path; it is imported only for interactive `copout pick`.
- Fetch daemon output only for commands selected by `copout pick`, rather than hydrating the entire candidate window.

### Output and daemon reliability

- Upgrade to Jerakeen 0.10.0 and Atuin daemon protocol 3; captured output is now retrieved through `History.GetCommandOutput` rather than the removed Semantic service.
- Report unsupported output RPCs and other retrieval errors instead of treating every failure as a missing capture.
- Read CLI history before opening daemon clients during diagnostics, avoiding subprocess forks after gRPC initialization.
- Start clipboard helpers before Jerakeen/gRPC access so normal clipboard delivery does not fork a new process after gRPC initialization; abort prestarted helpers without publishing an empty clipboard on retrieval failure.
- Add a live regression test that exercises the real clipboard path and requires clean stderr after gRPC output retrieval.
- Clarify that live-test probe commands must complete separately in the same shell session.
- Advance output schema to version 5. Output removes terminal-end whitespace, uses compact XML, formats durations with explicit units, recomputes normalized JSON byte counts, and reports Copout presentation truncation separately from Atuin capture truncation.
- Bound presented output for multi-run history records to 128 KiB per run and 512 KiB overall, preserving useful head and tail context with an explicit omission marker. Bare single-command output remains unbounded by Copout.
- Preserve XML-invalid text reversibly with explicit JSON-string markers and retain daemon truncation and byte-count metadata in the internal/JSON record.
- Bound daemon output and status requests to three seconds; retain history when output requests time out.
- Reconcile contributor instructions with the documented history CLI and public Jerakeen API boundary.
- Add XML round-trip, normalized-output, truncation, stalled-service, multi-command selection, output-budget, and inline-picker regression tests.

### Fixed

- Restore the documented copy/print CLI and synchronous console entry point, removing the experimental future-history tail path.
- Align the package version with project metadata and repair stale test assumptions.
- Exercise the installed command with controlled service and clipboard processes, and provide opt-in real shell capture checks.

### Changed

- Replaced Atuin MCP access with Atuin's documented history CLI for persisted session history and Jerakeen for direct daemon output access.
- Removed `copout install`; Copout no longer writes shell startup files or Atuin configuration.
- `copout doctor` is read-only and reports exact Atuin configuration remediation commands; `copout verify` is a concise end-to-end assertion.
- Removed production dependency-injection/factory plumbing that existed only for tests.
- Added typed command/history record schemas and removed defensive renderer shape recovery.
- Simplified structured output schema to version 3: redundant `capture` metadata was removed, provenance is represented by top-level `source` and per-run output `source`.
- Removed the Kitty watcher, Copout state directory, background writer, pending markers, command journal, retention logic, and watcher installation lifecycle.
