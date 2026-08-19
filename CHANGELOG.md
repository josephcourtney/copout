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

### Changed

- Adapt Atuin MCP history calls to both singular `filter_mode` schemas and Atuin 18.19's required plural `filter_modes` schema.
- Rebuilt Copout around Atuin as a hard dependency and authoritative command-history source.
- Removed the Kitty watcher, Copout state directory, background writer, pending markers, command journal, retention logic, and watcher installation lifecycle.
- Retrieve command history and command output through Atuin's public MCP interface.
- `copout install` enables the Atuin daemon and configures `pty-proxy` for zsh, bash, and fish.
- `copout doctor` and `copout verify` now diagnose Atuin history and output capture directly.
