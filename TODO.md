# TODO

## 0.12.0 release candidate (schema v9)

- [x] Preserve the v8 universal capture envelope while advancing the terminal-output contract to schema v9.
- [x] Keep upstream capture incompleteness distinct from explicit Copout presentation truncation.
- [x] Verify the 2,400-line probe evidence: Atuin retained the full snapshot; the prior 128 KiB Copout budget omitted the middle.
- [x] Increase the presentation budgets and add golden/unit regression coverage.
- [x] Add a collector that independently compares full Atuin snapshots, Kitty selection, and Copout's bounded presentation.
- [x] Move terminal evidence archives out of tracked project content; ignore future local ZIP bundles.
- [x] Choose 0.12.0 for the next candidate and align the package version, root lock metadata, README examples, and changelog.
- [x] Add `scripts/qualify_release.sh` with a no-skipped-live-tests gate and wheel/sdist inspection.
- [x] Document a human-observed Kitty/Atuin acceptance matrix in `docs/RELEASE_QUALIFICATION.md`.
- [ ] Run the candidate's `bash scripts/qualify_release.sh` **on the target macOS host**. Do not infer a pass from earlier validation on an older commit.
- [x] Complete the manual Kitty picker, selection, redirected output, and non-TTY acceptance steps (user-reported passing October 15; exact commit not recorded).
- [x] Complete the manual real-workload fidelity checks in `docs/RELEASE_QUALIFICATION.md` (user-reported passing October 15; evidence not independently re-inspected after PR #13).
- [ ] Record build artifacts, the exact checked commit, and the results of release qualification.
- [ ] Tag and publish **only on explicit request** after the gates pass.

## Follow-up hardening (not release blockers)

- [x] Implement automatic fresh-session setup and identity assertions in the real zsh/Atuin PTY tests. Actual macOS lifecycle validation remains pending.
- [x] Implement an opt-in multi-version Typer compatibility test matrix; **run it** before revising dependency bounds.
- [x] Implement a paired, stable-selection performance benchmark; **run it** before optimizing context capture.
- [x] Add regression tests proving old Atuin facts remain separate from Git state observed when Copout runs; continue requiring authoritative upstream historical sources.
- [x] Validate hardening on macOS: 192 pytest tests, four Typer versions, and a paired 10-command benchmark all passed October 15 (see `docs/HARDENING.md`).
- [ ] Preserve the one-file Ruff formatting change from the local `just fix` and recheck the pushed PR head before merge.
- [ ] Ensure the release qualification script/build artifact checks have passed on the final candidate revision before tagging.

## Prior 0.11.0 development

- [x] Implement selector-first CLI, stable preselection, bounded hydration, and picker stabilization.
- [x] Adopt schema v8's universal `runs` envelope.
- [x] Add real-shell PTY/stderr diagnostics and exercise 200- and 1000-command stress runs; no data loss reproduced under those conditions.
- [x] Update package/lock metadata and the dated 0.11.0 changelog section.
- [ ] If intermittent stderr loss recurs, preserve a real command, PTY observation, Atuin snapshot, and full execution context before proposing a production fix.

## Existing evidence

Earlier local `just fix` and `just check` passed without changes on the merged schema-v9 PR, before this release-candidate revision. Those results are useful but **do not** qualify this candidate commit. The former 0.10.0 validation on 2026-10-01 passed with 127 tests.
