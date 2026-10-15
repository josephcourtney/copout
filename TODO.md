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
- [x] Run `bash scripts/qualify_release.sh` on macOS at commit `7ea18711ab73fbca4eaea25694768d43ec68ea79` (October 15): 192 pytest tests, 14 explicit live-shell tests, headless CLI check, build and artifact inspections passed.
- [x] Complete the manual Kitty picker, selection, redirected output, and non-TTY acceptance steps (user-reported passing October 15; exact commit not recorded).
- [x] Complete the manual real-workload fidelity checks in `docs/RELEASE_QUALIFICATION.md` (user-reported passing October 15; evidence not independently re-inspected after PR #13).
- [x] Record artifacts and exact qualified revision in `docs/RELEASE_QUALIFICATION.md`; verified `dist/copout-0.12.0.tar.gz` and `dist/copout-0.12.0-py3-none-any.whl`.
- [x] Receive explicit authorization to tag and publish `v0.12.0` (October 15, 2026).
- [x] Finalize the dated `CHANGELOG.md` entry and GitHub release notes.
- [ ] Create and verify the `v0.12.0` Git tag against the final release commit.
- [ ] Publish and verify the GitHub release, including the rebuilt wheel and source distribution.

## Follow-up hardening (not release blockers)

- [x] Implement fresh-session setup and identity assertions in real zsh/Atuin PTY tests; explicit macOS live suite passed October 15.
- [x] Implement an opt-in multi-version Typer compatibility test matrix; **run it** before revising dependency bounds.
- [x] Implement a paired, stable-selection performance benchmark; **run it** before optimizing context capture.
- [x] Add regression tests proving old Atuin facts remain separate from Git state observed when Copout runs; continue requiring authoritative upstream historical sources.
- [x] Validate hardening on macOS: 192 pytest tests, four Typer versions, and a paired 10-command benchmark all passed October 15 (see `docs/HARDENING.md`).
- [x] Preserve Ruff formatting, validate clean merged head, and merge PR #14 as `7ea18711ab73fbca4eaea25694768d43ec68ea79`.
- [x] Qualify the final implementation revision (`7ea1871`) with `scripts/qualify_release.sh`; tagged/public release remains pending explicit request.

## Prior 0.11.0 development

- [x] Implement selector-first CLI, stable preselection, bounded hydration, and picker stabilization.
- [x] Adopt schema v8's universal `runs` envelope.
- [x] Add real-shell PTY/stderr diagnostics and exercise 200- and 1000-command stress runs; no data loss reproduced under those conditions.
- [x] Update package/lock metadata and the dated 0.11.0 changelog section.
- [ ] If intermittent stderr loss recurs, preserve a real command, PTY observation, Atuin snapshot, and full execution context before proposing a production fix.

## Existing evidence

The release candidate at `7ea18711ab73fbca4eaea25694768d43ec68ea79` passed the automated macOS release gate on 2026-10-15. Manual Kitty checks were reported passing earlier that day. Tag creation and GitHub release publication remain pending verification; the former 0.10.0 validation on 2026-10-01 passed with 127 tests.
