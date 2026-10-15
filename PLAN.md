# PLAN

## Current state

Copout is a small, invocation-driven adapter around Atuin. Atuin owns persisted command history, session identity, daemon lifecycle, and ephemeral rendered PTY snapshots. Jerakeen supplies the public Python interface to the daemon. Copout selects recent records, adds bounded read-only context, renders safe text in XML/JSON/Markdown, and copies or prints the results.

The **0.12.0 release candidate** incorporates the already merged schema-v9 work. This is **not** a tagged or published release. The package and lockfile version are 0.12.0, while the changelog retains those changes under *Unreleased* pending the macOS acceptance gate.

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

## Release qualification remaining

Use `docs/RELEASE_QUALIFICATION.md` as the acceptance record. The automated gate is `bash scripts/qualify_release.sh` and must run in the real macOS environment. Then exercise picker focus/selection/clipboard, redirected `-p`, explicit selectors, non-TTY failure, and the original Kev workload in Kitty. Record what was actually observed. The package build, live checks, and source-distro inspection cannot be certified merely by a green prior unit test suite.

Do not tag, publish, or mark the release qualified until all gates are observed. The release script deliberately does not release.

## Optional hardening

1. **Test-history isolation:** continue using authentic interactive shell startup until a dedicated Atuin session strategy is proven end to end. A custom `ATUIN_SESSION` value alone does not establish isolation from active daemon/session behavior.
2. **Typer bounds:** since Copout subclasses `TyperGroup`, validate upstream compatibility against a defined set of versions before adding an artificial upper bound. The locked version is covered by the current CLI tests.
3. **Context cost:** benchmark matched multi-run queries with context enabled and `--no-context` after warming output hydration; optimize only with reproducible measurements.
4. **Historical provenance:** only use authoritative upstream historical context. Do not present present-day Git/environment observations as historical state.

## Product boundary

Remain within `POLICY.md`:

- no Copout watcher, background daemon, journal, history database, or persistent output cache;
- no shell-startup, Git working-tree, or Atuin-configuration mutation by Copout;
- no direct access to Atuin's private database or daemon protocol;
- no default disclosure of sensitive/bulky remote URLs, hostnames, environment variables, executable paths, or diffs;
- distinguish historical source facts from current observations.

Any change requiring an exception needs an explicit policy/design decision before implementation.
