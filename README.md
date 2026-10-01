# Copout

Copout copies recent terminal history into the clipboard as compact XML, JSON, or readable Markdown. Atuin is the source of truth for command history and metadata; Atuin's daemon plus `pty-proxy` supply recent command output. Copout uses Atuin's documented history CLI for persisted session history and Jerakeen for direct daemon access to captured output.

Copout does **not** run a terminal watcher, maintain its own command journal, or modify shell or Atuin configuration.

## Requirements

- Python 3.13+
- Atuin 18.23.x on `PATH`
- Atuin shell integration
- For command output: Atuin daemon + `pty-proxy` + output capture enabled
- macOS `pbcopy`, Wayland `wl-copy`, or X11 `xclip`/`xsel`

Atuin's captured output is intentionally recent and ephemeral: the daemon keeps recent output locally and command history/metadata remain available independently. Copout treats missing captured output as unavailable rather than as an empty command result.

## Setup

Use Atuin's own output-capture setup command:

```console
atuin config enable output-capture
```

On Atuin 18.23 this enables the daemon when necessary, enables `pty_proxy.enabled` and `output.enabled`, and restarts an autostart-managed daemon so the capture backend picks up the new configuration. Follow any restart instructions printed by Atuin, then open a new shell.

Run a command and verify the complete path:

```console
printf 'copout output probe\n'
copout verify
```

`copout doctor` is read-only. It distinguishes configuration from runtime state and reports `daemon.enabled`, `daemon.autostart`, `pty_proxy.enabled`, `output.enabled`, whether pty-proxy is active in the current shell, daemon compatibility, and whether the latest command has captured output.

## Use

```console
copout                  # compact XML for the previous command
copout -p               # print instead of clipboard
copout --json           # JSON instead of XML
copout --markdown       # Markdown with fenced commands and output
copout pick 1 3 --markdown -p # print selected commands as Markdown
copout --pretty-attributes # put multiple XML attributes on separate lines
copout -n 5             # last five commands in the current Atuin session
copout --failure        # most recent failed command
copout pick             # inline checklist for recent commands
copout pick 1 3 6       # choose non-contiguous recent commands
copout pick 2-4 8       # ranges are inclusive
copout pick --limit 250 # browse farther back in the interactive picker
copout pick --preselect-records id1,id2 # open with exact Atuin records selected
copout --no-context     # omit all optional environment/repository context
copout --git-extended   # add worktree/upstream/divergence/remote/changed-file context
copout --git-diff       # add a bounded working-tree diff
copout --hostname-context # explicitly include the hostname
copout --env TERM --env LANG # explicitly include selected environment variables
copout --resolve git --resolve python # record resolved executable paths
copout doctor           # detailed integration diagnostics
copout verify           # concise history + output assertion
```

`copout pick` numbers candidate commands newest-first after excluding Copout commands: `1` is the same command selected by bare `copout`, `2` is the command before that, and so on. Selected runs are emitted chronologically. Explicit selectors are noninteractive. With no selectors, Copout opens a bounded inline checklist over the 100 most recent commands by default. Use Up/Down, Page Up/Page Down, Home/End to move, Space to toggle commands, Enter to copy the accumulated selection, and Esc or `q` to cancel without touching the clipboard. The list scrolls within the inline region rather than printing the entire candidate window into shell history.

Picker discovery reads only Atuin history metadata. Copout asks the daemon for output only after the selection is known, and then only for the selected commands. The Textual UI is imported only for interactive `copout pick`, so the normal `copout`, `-n`, and explicit `copout pick 1 4 6` paths do not pay its startup cost. Picker drawing is routed to the controlling terminal rather than structured stdout, so `copout pick -p > context.xml` remains usable; `copout pick 1 4 6 -p > context.xml` is fully noninteractive.

For shell integrations such as a runbook, `copout pick --preselect-records id1,id2,...` opens the normal picker with those exact Atuin record IDs already selected. The record IDs are the identity boundary: Copout does not try to match command text, and required records are included even when they fall outside the normal picker limit. Unknown IDs are rejected rather than silently ignored. This keeps the integration based on Atuin's existing command records without adding a Copout watcher or command journal.

Copout retrieves persisted chronological history with `atuin history list --session` and retrieves recent captured output from the Atuin daemon through Jerakeen. It does not access Atuin's private database or implement the daemon gRPC protocol itself.

Copout is presentation-focused. It removes ASCII whitespace only from the end of the complete captured output, which eliminates terminal-cell padding and final blank rows while preserving internal indentation, spacing, blank lines, and any SGR styling that survives Atuin's capture. XML is compact by default: routine byte counts and capture metadata are omitted for ordinary complete output. `--pretty-attributes` changes only XML layout, placing multiple attributes on separate indented lines; it does not change the data model.

For multi-run history records, presented output is bounded to 128 KiB per run and 512 KiB across all runs. Oversized output preserves both its beginning and end with an explicit omission marker. This presentation truncation is separate from Atuin capture truncation: JSON adds `presentation_truncated` and `presentation_omitted_bytes` when Copout shortens an output, while XML adds the same attributes to `<output>`. Bare single-command `copout` output is not subject to this presentation budget.

## Execution context

Schema version 7 can add compact environment and repository context. The defaults are intended to provide useful development context without automatically exposing hostnames, remotes, arbitrary environment variables, or large diffs.

Enabled by default:

- Git repository root, branch/detached state, commit, and dirty state for each run's recorded `cwd` when it is still accessible.
- Login shell path.
- OS family and architecture.
- Atuin session ID.
- Python executable, version, implementation, and active virtual environment when available.

Disabled by default:

- Hostname.
- Shell version and OS release/version.
- Extended Git details: Git/common directory, linked-worktree state, upstream, ahead/behind counts, remote URL, and changed filenames.
- Git working-tree diff. When enabled, it is bounded to 64 KiB and reports whether it was truncated.
- Arbitrary environment variables.
- Explicit executable resolution.

Git context is marked `observed_at_capture="true"`: it describes repository state when Copout creates the record, not necessarily repository state at the historical command's original timestamp. Historical `cwd`, command time, status, and duration continue to come from Atuin.

All extra context can be disabled with `--no-context`. Category overrides include `--no-git-context`, `--no-system-context`, `--no-python-context`, `--hostname-context`, `--shell-version`, `--os-version`, `--git-extended`, and `--git-diff`. `--env NAME` and `--resolve NAME` are repeatable and only expose values explicitly requested.

Copout reads persistent context settings from `$COPOUT_CONFIG` when set, otherwise `$XDG_CONFIG_HOME/copout/config.toml`, otherwise `~/.config/copout/config.toml`. `--config PATH` selects another file. An explicitly selected config path must exist. Command-line values override the file; repeated `--env` and `--resolve` values extend configured lists.

```toml
[context]
enabled = true
git = true
git_extended = false
git_diff = false
shell = true
shell_version = false
platform = true
os_version = false
hostname = false
session = true
python = true
env = []
executables = []
```

## Testing

Run `just check` for non-mutating lint, formatting, typing, and the test suite. `just repair` syncs dependencies, applies formatting and safe Ruff fixes, then runs type checking and tests without redundantly rerunning the Ruff validation passes. Add `--unsafe-fixes` to `just repair` or `just lint` to enable Ruff's unsafe fixes.

Command tests execute the installed `copout` launcher and module entry point in subprocesses, with a controlled Atuin executable, Jerakeen client, clipboard helper, and isolated config directory. They cover selection, normalized output, unavailable output, service errors, diagnostics, clipboard delivery, context configuration, and rendering without modifying your clipboard or history. The inline picker also has headless Textual interaction tests for navigation, multi-selection, confirmation, and cancellation.

The real shell capture test is self-contained. When `zsh` and `atuin` are available, pytest starts an interactive zsh in a PTY, lets the normal Atuin shell integration initialize, executes a standalone probe, waits across a separate command boundary for Atuin to finalize it, then verifies that Copout can retrieve the captured output. It skips only when the required shell/Atuin executable is unavailable; no manual probe or `COPOUT_LIVE_ATUIN` environment variable is required.

## Output format (schema version 7)

Copout's internal record retains capture metadata. JSON exposes that structured record after normalizing `output.text` by removing terminal-end ASCII whitespace. `captured_bytes` is recomputed from the presented text. `observed_bytes` is the upstream count of bytes observed before rendering when the backend supplies it. `total_bytes` is reserved for a true complete-output byte count and is left unknown when the backend cannot supply that fact. Atuin's current command-output RPC reports the size of its stored rendered output rather than the complete pre-truncation output size, so Copout does not map that value to `total_bytes`. Multi-run records may additionally report Copout presentation truncation as described above.

XML is deliberately compact. A typical command executed inside a Git repository can look like:

```xml
<copout version="7" captured_at="2026-10-01T09:31:00-04:00">
  <environment login_shell="/bin/zsh" os="macos" arch="arm64" session_id="...">
    <python executable="/repo/.venv/bin/python" version="3.14.0" implementation="cpython" environment="/repo/.venv"/>
  </environment>
  <run status="0" cwd="/repo" duration_ms="102" recorded_at="2026-10-01 09:30:59">
    <git observed_at_capture="true" root="/repo" branch="main" detached="false" commit="abc123..." dirty="false"/>
    <command><![CDATA[printf 'hello\n']]></command>
    <output><![CDATA[hello]]></output>
  </run>
</copout>
```

History XML has one `<run>` per selected command and does not repeat that count as a root attribute. Run durations are canonical integer milliseconds in `duration_ms`. `captured_at` records when Copout built the record, while `recorded_at` is the timestamp supplied by Atuin for the command. Structured optional context uses child elements: extended Git context may add worktree attributes plus `<changed-file>` and `<diff>`, while explicitly requested environment variables and executable resolutions appear as `<variable>` and `<executable>` children of `<environment>`.

### Text encoding contract

When an element has no `encoding` attribute, its XML character content is the presented UTF-8 text directly. CDATA is only an XML serialization detail; ordinary XML parsing recovers the text.

When an element has `encoding="json-string"`, concatenate/read its XML character content and JSON-decode it exactly once to recover the presented text. Copout uses this form when XML 1.0 cannot represent the text losslessly, including terminal control characters or carriage returns that XML parsing would otherwise normalize. Attribute values that need the same treatment use a companion marker such as `cwd_encoding="json-string"`.

"Presented text" means the text after Copout's terminal-end whitespace removal and any documented presentation truncation. It is therefore not necessarily byte-for-byte identical to the original PTY capture.

### Sparse output metadata

A normal complete capture remains compact:

```xml
<output><![CDATA[hello]]></output>
```

Extended attributes appear only when they explain an exceptional or incomplete capture. Supported attributes are:

- `state`: emitted when output is not in the normal captured state, currently `state="unavailable"`.
- `encoding`: emitted only when the element payload is a JSON string rather than literal XML character content.
- `truncated`: emitted as `true` when the upstream capture mechanism reports truncation.
- `captured_bytes`: byte length of the presented `<output>` text after decoding its transport encoding. It is emitted with extended incompleteness/truncation metadata, not on ordinary captures.
- `observed_bytes`: upstream count of bytes observed by the capture mechanism before rendering, when supplied and extended metadata is needed.
- `total_bytes`: true complete-output byte size, only when a backend can supply that fact independently. Copout does not infer it, and the current Atuin RPC's stored-rendered-output byte count is not used for this field.
- `exit_capture_complete`: whether the capture mechanism reports that capture remained active through process termination. Copout emits it only when the upstream API provides it and extended metadata is otherwise relevant; absence does not imply `true`.

Copout also retains `presentation_truncated` and `presentation_omitted_bytes` when Copout itself shortens a multi-run output to fit its presentation budget. That condition is independent of upstream `truncated`.

Unavailable output retains an `error` attribute when Copout knows why retrieval failed. Atuin-truncated output and Copout presentation truncation remain distinct.

Atuin's command capture is a terminal-rendered representation. Copout consumes that representation and does not attempt to intercept or reconstruct the underlying PTY stream or terminal input.

Daemon connection establishment, individual output requests, and status requests each have a three-second deadline. An unavailable or timed-out output request leaves usable history with output marked unavailable. A timed-out status request is reported by `copout doctor` and `copout verify`.

If output retrieval fails, the output record's `error` field (or XML attribute) preserves the reason. `UNIMPLEMENTED` means the daemon does not provide the output RPC expected by the installed Jerakeen client; it is not evidence of a missing capture or a disabled configuration flag. A healthy daemon status alone does not establish output API compatibility. `copout doctor` and `copout verify` report this distinction.
