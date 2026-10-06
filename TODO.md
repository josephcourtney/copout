# TODO

## 0.11.0 release

- [x] Complete the selector-first CLI and picker stabilization work.
- [x] Advance structured output to schema v8 with one universal `runs` envelope.
- [x] Add and stress-test real-shell stderr-capture diagnostics; no loss reproduced at 200 or 1000 rapid commands.
- [x] Bump package and lockfile metadata to 0.11.0.
- [x] Move the accumulated Unreleased changelog into the 0.11.0 release section.
- [x] Synchronize README/status documentation with the implemented behavior and current known concerns.
- [ ] Run `just repair` and final `just check` on the 0.11.0 release branch.
- [ ] Re-run the principal real-terminal workflows: bare picker, empty-selection Enter, multi-select, redirected `-p`, explicit selectors, and non-TTY failure behavior.
- [ ] Run `just build` and inspect the wheel/sdist.
- [ ] Tag/publish only when explicitly requested.

## Unconfirmed stderr observation

- [x] Add real-shell/Atuin E2E probes that preserve both the child-PTY observation and Atuin/Copout result.
- [x] Exercise stderr from shell builtins, child processes, direct fd 2 writes, buffered bursts, nonzero exits, pipelines, redirected stdout, missing final newlines, and mixed stdout/stderr.
- [x] Run rapid independent stderr probes at counts of 200 and 1000 without reproducing loss.
- [ ] If the behavior recurs, capture the exact command and execution context and classify the failure as missing Atuin history, unavailable daemon output, or terminal-visible data absent from Atuin-retrieved output before changing production code.

## Follow-up design decisions

- [ ] Review whether real-shell integration tests can use a dedicated Atuin session identity to reduce side effects in normal user history without weakening coverage.
- [ ] Consider an upper Typer compatibility bound because Copout subclasses `TyperGroup`; update the lockfile and validate locally if changed.
- [ ] Measure context-capture subprocess cost on large multi-run selections; optimize only if measurement shows it is material.
- [ ] Consider additional historical context only when it can come from an authoritative upstream source.
- [ ] Keep optional context additions privacy-conservative and bounded; avoid adding persistent Copout state to support them.

## Previous release validation

0.10.0 release validation on 2026-10-01: `just repair` and `just check` both passed with 127 tests; the only resulting working-tree change was the expected `uv.lock` version update from 0.9.3 to 0.10.0.
