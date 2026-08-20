# POLICY.md

## Product boundary

Copout exists to make recent terminal context easy to paste elsewhere. It is not a history database.

Atuin owns command history, command metadata, session identity, and recent PTY-captured output. Copout owns only selection, assembly, presentation, clipboard delivery, setup assistance, and diagnostics.

## Compatibility

Atuin is a hard dependency. Copout reads persisted chronological history through Atuin's documented `history list` CLI. Command-output capture requires an Atuin release that provides the daemon and `pty-proxy`; Copout reaches that daemon through Jerakeen's public Python API.

Copout does not use Atuin's MCP server, private SQLite schema, or private daemon protocol, and it does not import Jerakeen's private protobuf modules.

## Privacy

Copout does not persist command output. It requests output only when invoked. Atuin's own retention and privacy behavior governs the underlying history and output cache.

## Releases

User-visible behavior changes belong in `CHANGELOG.md`. Keep development infrastructure proportional to the size of the project.
