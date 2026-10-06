# PLAN

## Current state

Copout is a small, invocation-driven adapter around Atuin. Atuin remains the source of truth for persisted command history, session identity, and recent PTY-captured output; Jerakeen provides the public Python interface to the Atuin daemon. Copout selects records, optionally enriches them with read-only execution context, renders structured output, and delivers it to stdout or the clipboard.

The 0.11.0 release candidate includes:

- compact XML schema version 8 plus JSON and Markdown renderers, using one universal capture envelope with a non-empty `runs` array;
- selector-first CLI UX: bare `copout` opens the interactive picker, while root positional selectors gather exact recent-history positions noninteractively;
- relative TUI preselection through `--preselect` and stable Atuin record-ID preselection through `--preselect-records`;
- bounded Textual selection with arrow and Vim-style navigation;
- recent-command and arbitrary multi-command selection, with explicit selectors independent of the TUI browse-window limit;
- lazy output hydration after picker or selector resolution, with bounded concurrent daemon requests;
- configurable, privacy-conservative execution-context capture;
- read-only diagnostics and end-to-end verification;
- bounded presentation of large output;
- self-contained real-shell/Atuin PTY integration tests, including targeted stderr-capture diagnostics;
- local repair/check workflows through `just`.

## Completed for 0.11.0

The selector-first redesign, picker navigation and preselection, empty-selection Enter behavior, stable-ID window expansion, Copout-command filtering, bounded output hydration, and config-precedence regression coverage are complete.

Schema v8 replaces the distinct command/history record shapes with one capture envelope. Every successful capture has root capture metadata plus a non-empty `runs` array. The schema removes `scope` and the old `history` summary, always carries each run's Atuin `history_id`, and applies the same presentation-budget rules regardless of selection syntax or run count.

The reported intermittent stderr-loss behavior was investigated with real zsh + Atuin + pty-proxy tests. The suite covers shell builtins, child processes, direct fd 2 writes, buffered bursts, nonzero exits, pipelines, redirected stdout, missing final newlines, mixed stdout/stderr ordering, and rapid independent commands. No loss reproduced in the normal suite, a 200-command stress run, or a 1000-command stress run. The diagnostic tests remain as regression/reproduction coverage; no production capture change is justified without a concrete failing case.

## 0.11.0 release validation

1. Run `just repair` and a final non-mutating `just check` after the version/metadata update.
2. Exercise the principal real-terminal workflows: bare picker, empty-selection Enter, multi-select, redirected `-p`, explicit selectors, and non-TTY failure behavior.
3. Run `just build` and inspect the resulting wheel/sdist before publication.
4. Tag/publish only when explicitly requested.

## Follow-up hardening

These are not known correctness bugs and are not blockers for 0.11.0:

1. Review whether the live-shell integration tests can use a dedicated Atuin session identity to reduce user-history side effects without weakening real integration coverage.
2. Consider an upper compatibility bound for Typer because Copout subclasses `TyperGroup`; make dependency/lockfile changes only with local validation.
3. Measure context-capture subprocess cost on large multi-run selections before optimizing it.
4. Consider additional historical context only when it can come from an authoritative upstream source; do not reconstruct old Git/environment state from current state.
5. Keep optional context additions privacy-conservative and bounded.

## Product boundary

Future work must remain within `POLICY.md`:

- no Copout watcher, daemon, journal, history database, or persistent output cache;
- no shell-startup or Atuin-configuration mutation;
- no direct access to Atuin's private database or daemon protocol;
- no default inclusion of sensitive/bulky context such as hostnames, remotes, arbitrary environment variables, executable-resolution details, or working-tree diffs;
- historical context should come from an authoritative upstream source rather than being reconstructed from current state.

If a proposed feature requires violating those constraints, it belongs in another tool or requires an explicit policy/design change before implementation.
