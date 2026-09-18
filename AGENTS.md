# AGENTS.md

Copout is intentionally small. Atuin is the authoritative source for command history and recent command output; Copout selects, formats, diagnoses, and copies that data.

## Architecture constraints

- Do not add a Copout terminal watcher, command database, journal, daemon, or persistent history cache.
- Read persisted session history through Atuin's documented `history list` CLI. Use Jerakeen's public Python API for daemon status and ephemeral command output.
- Do not access Atuin's private SQLite schema or implement its daemon socket protocol in Copout. Jerakeen owns daemon transport and protocol compatibility.
- Command output may be unavailable because Atuin's daemon output cache is ephemeral. Treat this as a supported partial-data state, not a reason to persist output in Copout.
- Keep shell-configuration changes minimal and idempotent.

## Validation

Run `just check` for substantive changes. Use targeted pytest tests while iterating. Do not claim checks passed if the required tool is unavailable.
