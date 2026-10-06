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

Copout has two primary selection modes: no explicit selection opens the interactive picker, while positional selectors gather exactly the requested history entries without opening the TUI.

```console
copout                         # open the interactive picker
copout 1                       # latest non-Copout command, noninteractive
copout 1 3 6                   # gather non-contiguous recent commands
copout 2-4 8                   # inclusive ranges
copout 1,4,7                   # comma-separated selectors also work
copout 1 3-5 9 --markdown      # selectors compose with output options
copout 2-5 --json -p           # print selected history as JSON

copout -n 5                    # last five commands, noninteractive
copout --failure               # most recent failed command
copout -n 3 --failure          # last three failed commands

copout --preselect 1,3         # TUI with relative entries 1 and 3 selected
copout --preselect 1 --preselect 5-7
copout --preselect-records id1,id2 # TUI with exact Atuin records selected
copout --preselect 1-3 --preselect-records id1 # union both preselection forms
copout --limit 250             # browse farther back in the TUI

copout --markdown              # open TUI; render the chosen result as Markdown
copout --json                  # open TUI; render the chosen result as JSON
copout -p                      # open TUI; print instead of copying after confirmation
copout --pretty-attributes     # open TUI; pretty-print multi-attribute XML elements

copout pick                    # compatibility spelling for the interactive picker
copout pick 1 3                # compatibility spelling for explicit selectors
copout doctor                  # detailed integration diagnostics
copout verify                  # concise history + output assertion
```

Selectors are 1-based and newest-first after excluding Copout commands: `1` is the newest eligible command, `2` is the one before that, and so on. Selected runs are emitted chronologically. Explicit selectors are always noninteractive and automatically enlarge history discovery far enough to resolve the oldest requested position, so `copout 250` does not require `--limit 250`.

`--limit` controls only the TUI browse window, which defaults to 100 entries. With no explicit selection query, Copout opens a bounded inline checklist. Use Up/Down or `j`/`k` to move one entry, Home/End or `g`/`G` to jump to the ends, Page Up/Page Down or `Ctrl-U`/`Ctrl-D` to move by a page, Space to toggle commands, Enter to copy or print the accumulated selection (or the most recent eligible command when nothing is selected), and Esc or `q` to cancel without touching the clipboard. The list scrolls within the inline region rather than printing the entire candidate window into shell history.

`--preselect` uses the same relative selector grammar as noninteractive positional selection, but opens the TUI instead of finalizing the selection. It is repeatable and also accepts comma-separated values. `--preselect-records` addresses exact Atuin record IDs and is intended for integrations that need stable identity rather than a relative history offset. The two preselection forms may be combined and their selections are unioned. Preselection cannot be combined with positional selectors, `-n`, or `--failure`, because those already define a completed noninteractive query.

Formatting, output-delivery, and context options are orthogonal to selection. Options may appear before a root positional selector or after it; for example, `copout --markdown 1 3` and `copout 1 3 --markdown` have the same meaning.

Picker discovery reads only Atuin history metadata. Copout asks the daemon for output only after the selection is known, and then only for the selected commands. The Textual UI is imported only when an interactive picker is actually opened. Picker drawing is routed to the controlling terminal rather than structured stdout, so redirected semantic output remains clean after confirmation. A bare or preselected interactive invocation without a controlling terminal fails explicitly rather than silently changing selection behavior; scripts should use positional selectors, `-n`, or `--failure`.

Copout retrieves persisted chronological history with `atuin history list --session` and retrieves recent captured output from the Atuin daemon through Jerakeen. It does not access Atuin's private database or implement the daemon gRPC protocol itself.

## Presentation behavior

Copout removes ASCII whitespace only from the end of complete captured output. This eliminates terminal-cell padding and final blank rows while preserving internal indentation, spacing, blank lines, and any SGR styling that survives Atuin's capture.

Presented output is bounded to 128 KiB per run and 512 KiB across all runs, including captures containing only one run. Oversized output preserves both its beginning and end with an explicit omission marker. JSON adds `presentation_truncated` and `presentation_omitted_bytes` when Copout shortens an output, while XML adds the same attributes to `<output>`. This presentation truncation is separate from any truncation reported by Atuin. Because schema v8 uses one universal envelope, the presentation rules no longer depend on whether a command was selected with `-n 1`, a positional selector, or the TUI.

## Execution context

Schema version 8 can add compact environment and repository context. The defaults are intended to provide useful development context without automatically exposing hostnames, remotes, arbitrary environment variables, or large diffs.

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

## Output format (schema version 8)

Schema v8 has one record shape for every capture. The root contains capture metadata plus a non-empty `runs` array; a single selected command is represented by a one-element `runs` array, exactly like one run within a larger selection. The schema no longer has `scope`, distinct command/history record types, or the old `history` summary object. Query intent is not encoded into the result shape.

Copout's internal record retains capture metadata. JSON exposes that structured record after normalizing each `output.text` by removing terminal-end ASCII whitespace. `captured_bytes` is recomputed from the presented text. `observed_bytes` is the upstream count of bytes observed before rendering when the backend supplies it. `total_bytes` is reserved for a true complete-output byte count and is left unknown when the backend cannot supply that fact. Atuin's current command-output RPC reports the size of its stored rendered output rather than the complete pre-truncation output size, so Copout does not map that value to `total_bytes`.

A typical XML history result can look like:

```xml
<copout version="8" captured_at="2026-10-01T09:31:00-04:00">
  <environment login_shell="/bin/zsh" os="macos" arch="arm64" session_id="...">
    <python executable="/repo/.venv/bin/python" version="3.14.0" implementation="cpython" environment="/repo/.venv"/>
  </environment>
  <run history_id="..." status="0" cwd="/repo" duration_ms="102" recorded_at="2026-10-01 09:30:59">
    <git observed_at_capture="true" root="/repo" branch="main" detached="false" commit="abc123..." dirty="false"/>
    <command><![CDATA[printf 'hello\n']]></command>
    <output><![CDATA[hello]]></output>
  </run>
</copout>
```

XML has one `<run>` per selected command, including for a one-command capture, and every run carries its Atuin `history_id`. It does not repeat the run count as a root attribute. Run durations are canonical integer milliseconds in `duration_ms`. `captured_at` records when Copout built the record, while `recorded_at` is the timestamp supplied by Atuin for the command. Structured optional context uses child elements: extended Git context may add worktree attributes plus `<changed-file>` and `<diff>`, while explicitly requested environment variables and executable resolutions appear as `<variable>` and `<executable>` children of `<environment>`.

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

Copout also retains `presentation_truncated` and `presentation_omitted_bytes` when Copout itself shortens output to fit its presentation budget. That condition is independent of upstream `truncated`.

Unavailable output retains an `error` attribute when Copout knows why retrieval failed. Atuin-truncated output and Copout presentation truncation remain distinct.

Atuin's command capture is a terminal-rendered representation. Copout consumes that representation and does not attempt to intercept or reconstruct the underlying PTY stream or terminal input.

Daemon connection establishment, individual output requests, and status requests each have a three-second deadline. An unavailable or timed-out output request leaves usable history with output marked unavailable. A timed-out status request is reported by `copout doctor` and `copout verify`.

If output retrieval fails, the output record's `error` field (or XML attribute) preserves the reason. `UNIMPLEMENTED` means the daemon does not provide the output RPC expected by the installed Jerakeen client; it is not evidence of a missing capture or a disabled configuration flag. A healthy daemon status alone does not establish output API compatibility. `copout doctor` and `copout verify` report this distinction.

## Testing

Run `just check` for non-mutating lint, formatting, typing, and the test suite. `just repair` syncs dependencies, applies formatting and safe Ruff fixes, then runs type checking and tests without redundantly rerunning the Ruff validation passes. Add `--unsafe-fixes` to `just repair` or `just lint` to enable Ruff's unsafe fixes.

Command tests execute the installed `copout` launcher and module entry point in subprocesses with a controlled Atuin executable, Jerakeen client, clipboard helper, and isolated config directory. They cover root selector dispatch, direct and preselected selection, normalized output, unavailable output, service errors, diagnostics, clipboard delivery, context configuration, rendering, and selector window expansion without modifying the user's clipboard or history. The inline picker has headless Textual interaction tests for arrow and Vim navigation, multi-selection, confirmation, preselection, and cancellation.

The real shell capture test is self-contained. When `zsh` and `atuin` are available, pytest starts an interactive zsh in a PTY, lets the normal Atuin shell integration initialize, executes a standalone probe, waits across a separate command boundary for Atuin to finalize it, then verifies that Copout can retrieve the captured output. It skips only when the required shell/Atuin executable is unavailable.
