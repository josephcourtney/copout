# POLICY.md

## Product boundary

Copout exists to make recent terminal context easy to paste elsewhere. It is not a history database or an Atuin configuration manager.

Atuin owns command history, command metadata, session identity, daemon lifecycle, `pty-proxy`, and recent PTY-captured output. Jerakeen owns the Python interface to Atuin's daemon. Copout owns only selection, assembly, presentation, clipboard delivery, and read-only diagnostics.

Copout must not modify shell startup files or Atuin configuration. Diagnostics may report required settings and print commands the user can run explicitly.

## Compatibility

Atuin is a hard dependency. Persisted history is read through Atuin's documented CLI. Command-output capture requires an Atuin release that provides the daemon and `pty-proxy`, and Copout accesses that daemon through Jerakeen's public Python API.

## Privacy

Copout does not persist command output. It requests output only when invoked. Atuin's own retention and privacy behavior governs the underlying history and output cache.

## Releases

User-visible behavior changes belong in `CHANGELOG.md`. Keep development infrastructure proportional to the size of the project.
