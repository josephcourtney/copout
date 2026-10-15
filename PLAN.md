# PLAN

## Current state

Copout is a small, invocation-driven adapter around Atuin. Atuin owns persisted command history, session identity, daemon lifecycle, and ephemeral rendered PTY snapshots. Jerakeen supplies the public Python interface to the daemon. Copout selects recent records, adds bounded read-only context, renders safe text in XML/JSON/Markdown, and copies or prints the results.

The **0.12.0 release candidate** incorporates the merged schema-v9 and optional hardening work. It passed macOS release qualification on October 15 at commit `7ea18711ab73fbca4eaea25694768d43ec68ea79`. This is **not** a tagged or published release; the changelog remains under *Unreleased* until an explicitly authorized release.

## Completed implementation

- A universal `runs` envelope for single- and multi-command captures, originally introduced in schema v8.
- Bare picker, direct relative selectors, stable Atuin record-ID TUI preselection, empty-selection Enter, chronological multi-select, and bounded output hydration.
- XML/JSON/Markdown renderers with safe terminal escape normalization, schema v9 provenance, separate raw snapshot/presented byte counts, and explicit unknown/incomplete/unavailable upstream completeness.
- Fair output budgets of 256 KiB per run and 1 MiB total; independently flagged Copout presentation truncation and upstream limitations.
- A diagnostic heuristic when observed PTY traffic greatly exceeds rendered snapshot size, without treating those non-equivalent byte counts as proof of loss.
- Real-shell/Atuin end-to-end tests for stderr, child processes, pipelines, redirected stdout, buffering, nonzero exits, and rapid captures. Prior stress probes at 200 and 1000 commands did not reproduce missing stderr.
- Unit/golden tests, self-contained 2400-line terminal-output probe, and an evidence collector that compares the raw Atuin snapshot, normalized Atuin text, Copout presentation, and optional Kitty selection.
- Removal of the committed terminal-evidence ZIP from the current Git tree, with an ignore pattern to prevent recurrence.
- A non-publishing macOS release-qualification script that rejects missing/skipped live tests and inspects wheel/sdist contents and versions.

The uploaded Oct 15 diagnostic probe confirmed all 2,400 lines and both markers were retained upstream by Atuin; Copout's earlier 128 KiB presentation budget omitted the middle. The revised 256 KiB limit fits that probe. This conclusion does not certify completeness for arbitrary redrawing/interactive sessions.

## Release qualification

On October 15, the user completed the manual Kitty acceptance matrix and ran `bash scripts/qualify_release.sh` on macOS against `7ea1871`. Ruff, `ty`, 192 tests, the separate 14-test live suite, headless checks, and wheel/sdist inspections passed. The two build artifacts are `dist/copout-0.12.0-py3-none-any.whl` and `dist/copout-0.12.0.tar.gz`. See `docs/RELEASE_QUALIFICATION.md` for the acceptance record.

The candidate is qualified. No release tag or publication has been requested or performed. The release script deliberately does not release.

## Optional hardening

All four safeguards are **implemented** as tests or opt-in diagnostics, not as unmeasured production changes. See `docs/HARDENING.md`.

1. **Test-session isolation:** the native zsh/Atuin live harness resets session/proxy inheritance in the forked child, obtains a fresh shell identity, and verifies that Copout's result uses it. The live suite passed on macOS; this scopes session queries, not global Atuin persistence.
2. **Typer compatibility:** `just typer-compat` constructs temporary environments around the 0.26.0 vendored-Click boundary, running the CLI test matrix. Do not add speculative dependency bounds before reviewing actual results.
3. **Context cost:** `just benchmark-context` alternates matched, same-history-ID runs with and without read-only context and reports robust aggregate latency comparisons. Optimize only if the measured delta justifies it.
4. **Historical provenance:** regression tests require historical Atuin timestamps and statuses to remain distinct from Git state observed at capture. Introduce new historical fields only from authoritative upstream evidence.

## Product boundary

Remain within `POLICY.md`:

- no Copout watcher, background daemon, journal, history database, or persistent output cache;
- no shell-startup, Git working-tree, or Atuin-configuration mutation by Copout;
- no direct access to Atuin's private database or daemon protocol;
- no default disclosure of sensitive/bulky remote URLs, hostnames, environment variables, executable paths, or diffs;
- distinguish historical source facts from current observations.

Any change requiring an exception needs an explicit policy/design decision before implementation.
