# Capture diagnostics: design, implementation and qualification

## Purpose and boundaries

Make silent omissions visible while preserving Copout's invocation-only role. Capture diagnostics are **not** a second history source or a transcript validator: Atuin retains command history, and its ephemeral output RPC yields a terminal-rendered snapshot, which may exclude scrollback even when its truncation flag is false. Diagnostics inspect Copout's in-memory capture and rendered projection; no monitoring, persistence, new daemon queries, or upstream protocol access is introduced.

Diagnostics stay outside the schema-v9 XML/JSON/Markdown output and are sent only to stderr. Existing capture invocations remain silent unless explicitly requested; this avoids noise in interactive use, scripts, and clipboard actions. No schema bump or package-version change is required.

## User-facing contract

| Mode | Report | Delivery | Exit code |
| --- | --- | --- | --- |
| Default | None | As before | As before |
| `--diagnostics` | Aggregate inventory and findings on stderr | As before | As before |
| `--diagnostics-verbose` | Aggregate plus per-run byte/line counts and findings | As before | As before |
| `--check` | Aggregate report on stderr | Only when no error/partial defect | 4 on validation failure, otherwise normal |
| `--check --diagnostics-verbose` | Detailed report | Same strict behavior | Same strict behavior |

These flags work with `-n`, `--failure`, positional selectors, `pick`, and TUI selections. Root options are inherited by the explicit `pick` subcommand. No output is emitted for a canceled picker. On strict failure, nothing goes to stdout and the clipboard helper is **not started**; on strict success, copying or printing proceeds normally. Exit codes 2 (selection/usage), 3 (Atuin), and 127 (clipboard startup) retain their meanings.

Example:

```console
copout 1 3 --diagnostics --print
copout --last 8 --diagnostics-verbose --markdown
copout pick 2-5 --check
```

## Diagnostic inputs and analysis stages

1. **Selection intent:** The noninteractive `--last N` selection provides a requested count; explicit positional/TUI selections provide their exact selected history IDs. A shorter actual selection is classified as partial, and mismatched IDs/order are invalid. Candidate-query totals are not inferred from the requested selection count.
2. **Raw assembled record:** For each run, collect UTF-8 command length and line count, original output length and availability, unique history IDs, upstream completeness/truncation/exit signals, and the PTY-traffic coverage heuristic.
3. **Rendered projection:** Reuse the *single* projection that XML, JSON, or Markdown rendering will actually serialize. Check preserved history ID/command/state; compare measured presented bytes with metadata; track per-run and total Copout omission sizes.
4. **Final payload:** Count actual encoded document bytes; do not confuse serialization overhead with raw/presented terminal bytes.
5. **Reporting:** Aggregate diagnostic classifications; optionally print content-free per-run metrics. Neither history commands, stdout/stderr content, environment values, nor output-retrieval error messages are included in the report.

Diagnostic work is performed only for opt-in modes. It adds no new Atuin or Jerakeen calls and never hydrates unselected candidates.

## Classification

- **Invalid (severity `error`):** duplicated IDs, selected ID mismatch, assembled/projection count or identity mismatch, empty command text, captured/presented byte-accounting mismatch, unavailable output carrying nonempty text, unsupported state, or inconsistent omission metadata.
- **Partial (severity `partial`):** requested count shortfall, unavailable snapshot, known upstream truncation or incomplete exit capture, or Copout presentation omission.
- **Advisory (severity `warning`):** very large PTY-observed-versus-snapshot discrepancy or unexpected output error accompanying an otherwise available snapshot.
- **No detected loss:** no invalid or partial evidence. This intentionally does **not** imply the upstream snapshot or entire Atuin history is complete.

`--check` fails for invalid or partial results. Advisory-only findings do not fail strict checking: PTY traffic contains terminal redraws, and the byte difference alone cannot establish dropped information. An unknown upstream completeness value is also *not* proof of completion and is reported per run in verbose mode.

An empty **captured** output is valid; `output=None` is unavailable even if the corresponding historical command returned exit 0. All byte counts use UTF-8, rather than Python character count. The "omitted" size is Copout's presentation-budget removal, not upstream missing bytes.

## Implementation structure

- `src/copout/capture_diagnostics.py`: immutable report/issue/run-stat objects, pure `inspect` and `format_report`; no I/O or history queries.
- `src/copout/render.py`: `render_with_projection` returns (text, normalized/budgeted record), with the established `render` interface delegated to it; the projection is computed exactly once per invocation.
- `src/copout/cli.py`: parse and inherit options, evaluate before delivery, print report to stderr, and defer clipboard startup in strict mode.
- `tests/test_capture_diagnostics.py`: normal/empty/missing output, Unicode, per-run/total truncation, upstream and advisory signals, identity/count/byte integrity, all presentation formats, CLI inheritance, and no clipboard mutation on strict failure.

## Qualification and future work

Before merging, run `just repair`, `just check`, `just release-check` (if defined by the current checkout), and perform two end-to-end macOS/Atuin smoke tests: (1) a short command with captured output under `--check`; (2) a record with absent daemon output under `--check`, checking exit 4 and unchanged clipboard. Repeat `--diagnostics --print` with piped stdout to verify stderr separation. This branch has not been locally validated against a live Atuin daemon.

Potential extensions should be evidence-driven: comparison with an independent PTY transcript/evidence collector, a machine-readable diagnostics stream, verified per-run history query cardinality when the documented upstream API supplies it, and measured capture/diagnostic overhead. Do **not** label the missing portions of a rendered terminal snapshot as quantified loss without an independent reference.
