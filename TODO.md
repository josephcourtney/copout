# TODO

## 0.10.0 release

- [x] Add configurable schema-v7 execution context.
- [x] Add stable Atuin-record preselection for external/runbook integrations.
- [x] Make the real Atuin shell-capture test self-contained under a PTY.
- [x] Keep `lint`/`format` mutating by default while preserving non-mutating `just check`.
- [x] Align `POLICY.md`, contributor guidance, README, changelog, and planning documents with the implemented architecture.
- [x] Bump package metadata to 0.10.0.
- [ ] Regenerate `uv.lock` after the version bump.
- [ ] Run `just repair` after the release-document/version changes and confirm the working tree is clean apart from intentional edits.
- [ ] Run `just check` as the final non-mutating release validation.
- [ ] Tag/publish 0.10.0 only when explicitly requested.

## Follow-up

- [ ] Add regression coverage for configuration precedence across defaults, config file, `COPOUT_CONFIG`, and CLI overrides if gaps remain after the 0.10.0 test audit.
- [ ] Review context-capture subprocess cost on large multi-run selections; optimize only if measurement shows it is material.
- [ ] Consider additional historical context only when it can come from an authoritative upstream source. Do not infer current Git/environment state to have existed when an old command ran.
- [ ] Keep optional context additions privacy-conservative and bounded; avoid adding persistent Copout state to support them.
