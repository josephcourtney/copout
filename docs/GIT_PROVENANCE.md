# Git provenance: event-time versus capture-time

## Observed behavior

Copout receives historical command ID, command text, timestamp, cwd, exit status, and duration from Atuin. When invoked, it probes the current Git working tree for each distinct historical cwd and attaches that snapshot to its selected runs. Consequently, several commands executed on different branches can show the **same current branch and HEAD**. This is not a reconstruction of historical Git state: the Git element is marked `observed_at_capture=true`.

The output's root `captured_at` records Copout assembly time; `run.recorded_at` is Atuin's historical command time. Do not equate these timestamps.

## Authority classes

| Field | Source | Time | Guarantee |
| --- | --- | --- | --- |
| `history_id`, `command`, `cwd`, status, duration, `recorded_at` | Atuin persisted command history | Execution | Historical facts as supplied by Atuin |
| `git.root`, `git.branch`, `git.commit`, `git.detached`, `git.dirty` | Copout read-only Git inspection | Copout capture | Current observations, explicitly marked `observed_at_capture=true` |
| Hypothetical execution-time Git state | Not currently provided | Unknown | **Unavailable**; never synthesize |

Copout must not infer execution-time branch or dirty state from a later HEAD, reflog, commit timestamp, command text, or a historical `cwd`. Reflogs can be expired, pruned or rewritten; multiple worktrees and detached heads make such reconstruction ambiguous.

## Planned upstream contract

If event-time Git provenance is useful, instrument **Atuin's existing shell/command lifecycle** rather than introducing a Copout watcher, journal, hooks, shell-file edits, or daemon. The authoritative event record should be associated with Atuin's immutable command history ID and include, when observed:

- `git_root` (repository identity), `commit` (full object ID), `branch` (optional symbolic ref), and `detached`.
- `dirty` only if actually inspected at the same lifecycle point; otherwise absent.
- Observation phase (`command_start` versus `command_end`), timestamp, and a stable source/observer identifier.
- Distinct unavailable/error state for non-repositories, inaccessible directories, timeout, or disabled instrumentation.
- A documented semantic decision about command start versus end: `git switch`, `git commit`, and `git checkout` may change Git state during a command.

**Atuin owns persistence and transport.** If Atuin adds this metadata, expose it through a documented Atuin history CLI field or a public Jerakeen-supported API. Copout must not read Atuin private tables or implement the daemon wire protocol. Atuin privacy policy and retention must govern these observations; Git remote URLs, diff content and arbitrary filenames must not be collected by default.

## Proposed presentation

Keep historical Git observations distinct from existing capture-time context; do not overload `observed_at_capture`, silently substitute null values, or mutate the meaning of `git`.

A **future versioned schema** could carry `git_at_execution` with `source=atuin`, `phase=command_start`, `observed_at=...`, and only fields actually delivered by upstream. Its absence means no evidence, not a clean repository or a successful observation. Existing `git` remains a current capture-time snapshot and continues to be labeled.

Do not ship the new field or bump the schema merely to support a hypothetical upstream API. A future implementation must be gated by actual observed provider data and validated end-to-end.

## Acceptance criteria

1. Execute a command on branch A, switch to branch B, execute a second command, then capture both. Each historical Git observation must match the appropriate command-time branch while capture-time context reflects the current branch.
2. Execute `git commit` and `git switch`: verify documented start/end phase semantics rather than arbitrarily choosing post-command Git state.
3. Include worktree, detached HEAD and non-repository cases. An unavailable execution-time state must remain absent, not be silently replaced by the current state.
4. Verify each observation is bound to the correct Atuin history UUID even for rapid commands and repeated command strings.
5. Verify that collection is bounded, read-only, privacy-conservative, and does not add Copout persistent state, watchers, shell hooks, direct daemon transport or database access.
6. Preserve the current schema-v9 contract until an upstream API and a versioned consumer change are both ready.

## Current implementation decision

**No upstream command-time Git observation is available through Copout's existing Atuin history interface.** Continue recording only explicit capture-time snapshots. Add genuine historical metadata only after confirming provider support and the event-time semantics. The earlier multi-run misleading appearance is addressed by clearer documentation now, not by fabricating historical state.
