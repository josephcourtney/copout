# AGENTS.md

Copout is intentionally small. Atuin is the authoritative source for command history and recent command output; Copout selects, enriches with read-only execution context, formats, diagnoses, and copies that data.

## Architecture constraints

- Do not add a Copout terminal watcher, command database, journal, daemon, or persistent history cache.
- Read persisted session history through Atuin's documented `history list` CLI. Use Jerakeen's public Python API for daemon status and ephemeral command output.
- Do not access Atuin's private SQLite schema or implement its daemon socket protocol in Copout. Jerakeen owns daemon transport and protocol compatibility.
- Command output may be unavailable because Atuin's daemon output cache is ephemeral. Treat this as a supported partial-data state, not a reason to persist output in Copout.
- Context enrichment must be observational. Do not modify Git repositories, shell startup files, Atuin configuration, or other external configuration.
- Distinguish historical data obtained from Atuin from state observed when Copout runs. Current Git/environment context must not be represented as historical command state.
- Keep privacy-sensitive or bulky context opt-in. In particular, do not enable hostnames, remote URLs, arbitrary environment variables, executable-resolution details, or working-tree diffs by default.
- Keep the structured output schema compact and explicit. Bump the schema version when changing its externally visible contract.

## Validation

Use targeted pytest tests while iterating. Run `just repair` after changes that can be safely auto-fixed; run `just check` for a final non-mutating validation pass when appropriate. Do not claim checks passed unless they were actually run successfully.

User-visible behavior changes belong in `CHANGELOG.md`. Keep `README.md`, `PLAN.md`, `TODO.md`, package version metadata, and schema documentation consistent with the implemented state before release.
