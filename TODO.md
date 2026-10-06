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
- [x] Run `just repair` and `just check` on `stabilize-selection-and-hydration` and merge only after both pass.

## Schema v8

- [x] Replace distinct command/history record shapes with one universal capture envelope.
- [x] Remove `scope` and the old `history` summary object.
- [x] Always expose selected commands through a non-empty `runs` array and include `history_id` consistently in XML.
- [x] Apply presentation budgets uniformly to one-run and multi-run captures.
- [x] Update renderer tests, CLI fixtures, README, changelog, and plan for schema v8.
- [x] Run local `just repair` and `just check` on `schema-v8-universal-envelope`, then merge only if both pass.

## Stderr capture investigation

- [x] Add real-shell/Atuin E2E probes for stderr-only output, child processes, direct fd 2 writes, nonzero exits, no-final-newline output, pipelines, redirected stdout, buffered bursts, mixed stdout/stderr ordering, and rapid independent commands.
- [x] Preserve each probe's observed child-PTY transcript so failures distinguish terminal emission from Atuin/Copout capture loss.
- [x] Make the rapid-probe count configurable through `COPOUT_STDERR_STRESS_COUNT` for targeted reproduction runs.
- [ ] Run the new suite on the affected real environment and repeat with a substantially larger stress count.
- [ ] If a failure reproduces, classify it as missing Atuin history, unavailable daemon output, or a sentinel present on the PTY but absent from Atuin-retrieved output before changing production code.

## Next release

- [ ] Update the package version only when the next release boundary is chosen; keep `uv.lock`, changelog, README, plan, and package metadata synchronized.
- [ ] Tag/publish only when explicitly requested.
- [ ] Re-run the real terminal workflows after merging stabilization: bare picker, empty-selection Enter, multi-select, redirected `-p`, explicit selectors, and non-TTY failure behavior.

## Follow-up design decisions

- [ ] Review whether the real-shell integration test can use a dedicated Atuin session identity to reduce side effects in the user's normal history without weakening the integration test.
- [ ] Consider an upper Typer compatibility bound because Copout subclasses `TyperGroup`; update the lockfile and validate locally if changed.
- [ ] Review context-capture subprocess cost on large multi-run selections; optimize only if measurement shows it is material.
- [ ] Consider additional historical context only when it can come from an authoritative upstream source. Do not infer current Git/environment state to have existed when an old command ran.
- [ ] Keep optional context additions privacy-conservative and bounded; avoid adding persistent Copout state to support them.

## Previous release validation

0.10.0 release validation on 2026-10-01: `just repair` and `just check` both passed with 127 tests; the only resulting working-tree change was the expected `uv.lock` version update from 0.9.3 to 0.10.0.
