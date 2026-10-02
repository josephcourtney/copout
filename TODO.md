# TODO

## Current stabilization

- [x] Make the TUI the default for bare `copout` while keeping explicit selectors noninteractive.
- [x] Preserve relative and stable-ID TUI preselection.
- [x] Add Vim-style picker navigation and default empty-selection Enter to history position `1`.
- [x] Reject empty history-count results instead of emitting successful zero-run records.
- [x] Recognize supported Copout module/wrapper invocation forms when filtering candidate history.
- [x] Extend stable-ID candidate windows contiguously so picker numbering remains accurate.
- [x] Bound concurrent Atuin output hydration requests.
- [x] Add config-path and CLI-over-config precedence regression coverage.
- [ ] Run `just repair` and `just check` on `stabilize-selection-and-hydration` and merge only after both pass.

## Next release

- [ ] Update the package version only when the next release boundary is chosen; keep `uv.lock`, changelog, README, plan, and package metadata synchronized.
- [ ] Tag/publish only when explicitly requested.
- [ ] Re-run the real terminal workflows after merging stabilization: bare picker, empty-selection Enter, multi-select, redirected `-p`, explicit selectors, and non-TTY failure behavior.

## Follow-up design decisions

- [ ] For schema v8, consider replacing the distinct single-command `CommandRecord` and one-run `HistoryRecord` shapes with one stable history envelope. Do not change schema-v7 shape implicitly.
- [ ] Review whether the real-shell integration test can use a dedicated Atuin session identity to reduce side effects in the user's normal history without weakening the integration test.
- [ ] Consider an upper Typer compatibility bound because Copout subclasses `TyperGroup`; update the lockfile and validate locally if changed.
- [ ] Review context-capture subprocess cost on large multi-run selections; optimize only if measurement shows it is material.
- [ ] Consider additional historical context only when it can come from an authoritative upstream source. Do not infer current Git/environment state to have existed when an old command ran.
- [ ] Keep optional context additions privacy-conservative and bounded; avoid adding persistent Copout state to support them.

## Previous release validation

0.10.0 release validation on 2026-10-01: `just repair` and `just check` both passed with 127 tests; the only resulting working-tree change was the expected `uv.lock` version update from 0.9.3 to 0.10.0.
