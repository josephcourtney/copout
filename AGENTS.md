# AGENTS.md

Copout is intentionally small. Atuin is the authoritative source for command history and recent command output; Copout selects, formats, diagnoses, and copies that data.

## Architecture constraints

- Do not add a Copout terminal watcher, command database, journal, daemon, or persistent history cache.
- Use Atuin's documented public interfaces. The current integration boundary is `atuin mcp` with runtime MCP tool discovery.
- Do not depend on Atuin's private SQLite schema or daemon socket protocol.
- Command output may be unavailable because Atuin's daemon output cache is ephemeral. Treat this as a supported partial-data state, not a reason to persist output in Copout.
- Keep shell-configuration changes minimal and idempotent.

## Validation

Run `just check` for substantive changes. Use targeted pytest tests while iterating. Do not claim checks passed if the required tool is unavailable.
