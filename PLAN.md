# PLAN

## Current state

Copout is a small, invocation-driven adapter around Atuin. Atuin remains the source of truth for persisted command history, session identity, and recent PTY-captured output; Jerakeen provides the public Python interface to the Atuin daemon. Copout selects records, optionally enriches them with read-only execution context, renders structured output, and delivers it to stdout or the clipboard.

The current codebase includes:

- compact XML schema version 7 plus JSON and Markdown renderers;
- selector-first CLI UX: bare `copout` opens the interactive picker, while root positional selectors gather exact recent-history positions noninteractively;
- relative TUI preselection through `--preselect` and stable Atuin record-ID preselection through `--preselect-records`;
- bounded Textual selection with arrow and Vim-style navigation;
- recent-command and arbitrary multi-command selection, with explicit selectors independent of the TUI browse-window limit;
- lazy output hydration after picker or selector resolution;
- configurable, privacy-conservative execution-context capture;
- read-only diagnostics and end-to-end verification;
- bounded presentation of large multi-run output;
- self-contained real-shell/Atuin PTY integration tests;
- local repair/check workflows through `just`.

## Next release tranche

1. Validate selector-first dispatch, relative/stable preselection, picker navigation, and legacy `pick` compatibility with `just repair` and `just check`.
2. Exercise the new bare-picker UX in a real terminal, including redirected `-p` output and non-TTY failure behavior.
3. Keep package/version metadata, lockfile, changelog, README, policy, contributor guidance, and schema documentation synchronized before a release bump.
4. Do not add release automation, CI, or publication machinery merely for this release; tag/publish only when explicitly requested.

## Post-release stabilization

Prioritize evidence from actual Copout use rather than speculative expansion.

1. Fix regressions in selection, context capture, rendering, clipboard delivery, and live Atuin integration before adding new surface area.
2. Measure context-capture overhead for multi-run selections before optimizing it.
3. Keep configuration precedence explicit and covered by tests: built-in defaults < config file < CLI overrides.
4. Preserve schema compactness. Add new fields only when they materially improve interpretation or reproducibility.
5. Keep context provenance explicit: Atuin-derived historical facts and capture-time observations are different kinds of information.

## Product boundary

Future work must remain within `POLICY.md`:

- no Copout watcher, daemon, journal, history database, or persistent output cache;
- no shell-startup or Atuin-configuration mutation;
- no direct access to Atuin's private database or daemon protocol;
- no default inclusion of sensitive/bulky context such as hostnames, remotes, arbitrary environment variables, executable-resolution details, or working-tree diffs;
- historical context should come from an authoritative upstream source rather than being reconstructed from current state.

If a proposed feature requires violating those constraints, it belongs in another tool or requires an explicit policy/design change before implementation.
