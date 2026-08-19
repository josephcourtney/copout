# POLICY.md

## Product boundary

Copout exists to make recent terminal context easy to paste elsewhere. It is not a history database.

Atuin owns command history, command metadata, session identity, and recent PTY-captured output. Copout owns only selection, assembly, presentation, clipboard delivery, setup assistance, and diagnostics.

## Compatibility

Atuin is a hard dependency. Command-output capture requires an Atuin release that provides `pty-proxy`, the daemon, and the MCP `atuin_output` capability. Copout discovers MCP tool schemas at runtime so minor Atuin schema evolution can be tolerated where practical.

## Privacy

Copout does not persist command output. It requests output only when invoked. Atuin's own retention and privacy behavior governs the underlying history and output cache.

## Releases

User-visible behavior changes belong in `CHANGELOG.md`. Keep development infrastructure proportional to the size of the project.
