# PLAN

## Current state

Copout is a small, invocation-driven adapter around Atuin. Atuin remains the source of truth for persisted command history, session identity, and recent PTY-captured output; Jerakeen provides the public Python interface to the Atuin daemon. Copout selects records, optionally enriches them with read-only execution context, renders structured output, and delivers it to stdout or the clipboard.

The 0.10.0 codebase includes:

- compact XML schema version 7 plus JSON and Markdown renderers;
- recent-command and arbitrary multi-command selection;
- stable Atuin record-ID preselection for external integrations;
- lazy output hydration after picker selection;
- configurable, privacy-conservative execution-context capture;
- read-only diagnostics and end-to-end verification;
- bounded presentation of large multi-run output;
- self-contained real-shell/Atuin PTY integration tests;
- local repair/check workflows through `just`.

## 0.10.0 release tranche

1. Keep package/version metadata, lockfile, changelog, README, policy, contributor guidance, and schema documentation synchronized.
2. Regenerate the lockfile after the 0.10.0 version bump.
3. Run `just repair`, then a final non-mutating `just check`.
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
