# POLICY.md

## Product boundary

Copout exists to make recent terminal context easy to paste elsewhere. It is not a history database, terminal watcher, shell manager, or Atuin configuration manager.

Atuin owns command history, command metadata, session identity, daemon lifecycle, `pty-proxy`, and recent PTY-captured output. Jerakeen owns the Python interface to Atuin's daemon. Copout owns selection, read-only context enrichment, assembly, presentation, clipboard delivery, and read-only diagnostics.

Context enrichment may inspect the current filesystem, Git repositories, process environment, and executable resolution. It must remain observational: Copout must not change repository state, shell startup files, Atuin configuration, or external tool configuration. Diagnostics may report required settings and print commands the user can run explicitly.

Copout must not add its own command journal, persistent history cache, terminal watcher, or background daemon. Historical facts should come from Atuin when Atuin provides them. Context observed only when Copout runs must be labeled so it is not presented as historical state.

## Compatibility

Atuin is a hard dependency. Persisted history is read through Atuin's documented CLI. Command-output capture requires an Atuin release that provides the daemon and `pty-proxy`, and Copout accesses that daemon through Jerakeen's public Python API.

Copout must not access Atuin's private database schema or implement its daemon transport/protocol directly.

## Privacy

Copout does not persist command output or captured execution context. It requests and assembles context only when invoked. Atuin's own retention and privacy behavior governs the underlying history and output cache.

Default context should be useful but privacy-conservative. Hostnames, remote URLs, arbitrary environment variables, executable-resolution details, and working-tree diffs must not be included by default. Potentially sensitive or bulky context must require explicit configuration or command-line opt-in, and bounded representations should be used where appropriate.

## Releases

User-visible behavior changes belong in `CHANGELOG.md`. Version metadata, schema documentation, planning/status documents, and examples must agree before a release is considered ready.

Keep development infrastructure proportional to the size of the project. Local validation through the documented `just` recipes is sufficient; do not add CI or release machinery without a concrete need.
