# Optional hardening

The commands here are **development diagnostics**, not new runtime services. They do not change Atuin configuration, add persisted capture state, or alter normal Copout output.

## Real-shell Atuin session isolation

`tests/test_live.py` starts a real interactive `zsh -il` in a new PTY, with the child-only inherited `ATUIN_SESSION`, `ATUIN_SHLVL`, `ATUIN_HISTORY_ID`, and proxy activation/socket markers unset. Normal Atuin shell integration must generate a fresh session identity. The harness retrieves the resulting value from the child's PTY, checks it is distinct from the parent's, and requires Copout's JSON context to report the same identity. A missing or reused identity is a hard failure, not a skipped test. Tests still exercise the actual configured daemon and pty-proxy.

**Scope of isolation:** tests query the new session rather than the caller's session. Atuin may still persist the child's commands in its global history database according to its normal retention settings. The harness **does not** mutate Atuin storage, daemon settings, dotfiles, or global history to erase traces, and it does not claim filesystem/storage isolation.

Run `uv run pytest tests/test_live.py -vv` on macOS with native Atuin/zsh integration to validate the lifecycle. The isolated-session guard is additionally covered by offline unit tests.

## Typer compatibility matrix

Copout overrides `TyperGroup.resolve_command`, which has compatibility risk across Typer releases. Typer 0.26.0 vendors Click; test versions on both sides of that change before changing dependency bounds.

```console
just typer-compat
# Or choose specific versions:
uv run python scripts/check_typer_compatibility.py --versions 0.24.1 0.26.0 0.27.2 0.27.3
```

Each version receives a temporary uv-created virtual environment and an editable Copout install. The script runs the installed-entrypoint, selector, and CLI component tests, prints PASS/FAIL by version, and exits nonzero if any version fails. All temporary virtual environments are deleted on exit. Internet/dependency availability is required for uncached versions. Test failures or installation failures must be distinguished before declaring a version incompatible.

The project's locked Typer version was **0.27.2** when this matrix was added. The 0.27.3 column tests the October 6, 2026 release. No speculative upper bound is imposed until the actual compatibility results support one.

## Context-capture timing

```console
just benchmark-context
# For reproducible aggregate JSON output:
uv run python scripts/benchmark_context.py --count 10 --warmups 3 --pairs 20 --json-output /tmp/copout-context-benchmark.json
```

Requires an active Atuin session with at least the chosen number of eligible commands. Each warmup/trial calls the real Copout CLI twice on the **same selected history IDs**, with context enabled and disabled. The order alternates to reduce warm-cache bias. A changed selection or CLI error aborts the benchmark. It reports median/p90 total CLI latency and median overhead; these timings include history loading, hydration, process startup, and rendering, **not just Git subprocess execution**.

The tool holds command output only in memory and by default prints aggregate numbers, not command strings or captured text. The optional report file contains aggregates. For meaningful comparisons, repeat on the same host and stable Atuin daemon conditions; do not treat one run as an optimization mandate.

## Historical provenance

Atuin supplies each run's historical timestamp, status, cwd, and duration. Copout's Git and environment enrichment inspects the **current** filesystem and process only when invoked. The Git record therefore carries `observed_at_capture=true`, while the output envelope distinguishes `captured_at` from Atuin's `recorded_at`.

Regression tests build records with old Atuin timestamps and a known current Git commit, verifying that XML/JSON retain both provenance classes rather than presenting current Git state as historical. Additional historical fields should be introduced only when a trusted upstream supplies an authoritative observation; no reconstructed guesses or shell/git hook mutations are added.
