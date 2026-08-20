# AGENTS.md

Copout is intentionally small. Atuin is the authoritative source for command history and recent command output; Copout selects, formats, diagnoses, and copies that data.

## Architecture constraints

- Do not add a Copout terminal watcher, command database, journal, daemon, or persistent history cache.
- Use documented public integration boundaries only: Atuin's `history list` CLI for persisted chronological history and Jerakeen's public Python API for Atuin daemon access.
- Do not start or depend on `atuin mcp`.
- Do not import `jerakeen._proto`, depend on Atuin's private SQLite schema, or implement the daemon socket protocol in Copout.
- Command output may be unavailable because Atuin's daemon output cache is ephemeral. Treat this as a supported partial-data state, not a reason to persist output in Copout.
- Keep shell-configuration changes minimal and idempotent.

## Validation

Run `just check` for substantive changes. Use targeted pytest tests while iterating. Do not claim checks passed if the required tool is unavailable.
