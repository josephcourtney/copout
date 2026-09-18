# Changelog

## 0.7.4 - 2026-08-19

- Parse Atuin 18.19 MCP history's documented Markdown text response instead of assuming JSON structured content.
- Extract terminal output from the `Selected output` section and remove Atuin line-number prefixes.
- Distinguish missing `ATUIN_SESSION` from an actual empty session in `copout doctor`.

## 0.7.3 - 2026-08-19

### Fixed

- Narrow structured renderer sections before access so `ty` can prove they are mappings/lists.
- Accept structural MCP client factories, allowing typed test doubles without coupling them to the concrete client class.

## 0.7.2

- Fix Atuin MCP history retrieval by omitting optional empty search queries.
- Continue adapting history filter arguments to the live Atuin MCP schema.

## Unreleased

### Fixed

- Restore the documented copy/print CLI and synchronous console entry point, removing the experimental future-history tail path.
- Align the package version with project metadata and repair stale test assumptions.
- Exercise the installed command with controlled service and clipboard processes, and provide an opt-in real shell capture check.

### Changed

- Replaced Atuin MCP access with Atuin's documented history CLI for persisted session history and Jerakeen for direct daemon output access.
- Removed `copout install`; Copout no longer writes shell startup files or Atuin configuration.
- `copout doctor` is read-only and reports exact Atuin configuration remediation commands; `copout verify` is a concise end-to-end assertion.
- Removed production dependency-injection/factory plumbing that existed only for tests.
- Added typed command/history record schemas and removed defensive renderer shape recovery.
- Simplified structured output schema to version 3: redundant `capture` metadata was removed, provenance is represented by top-level `source` and per-run output `source`.
- Removed the Kitty watcher, Copout state directory, background writer, pending markers, command journal, retention logic, and watcher installation lifecycle.
