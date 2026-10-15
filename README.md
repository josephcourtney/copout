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

Copout presents Atuin's retained terminal snapshot as safe plain text across XML, JSON, and Markdown. It removes ANSI styling and interprets common carriage-return, backspace, cursor, and erase-line redraws. Internal newlines are retained, while terminal-end padding is removed. This normalization cannot recover scrollback or earlier output absent from Atuin's stored snapshot.

Presented output is bounded to 128 KiB per run and 512 KiB across all runs, including captures containing only one run. Oversized output preserves both its beginning and end with an explicit omission marker. JSON adds `presentation_truncated` and `presentation_omitted_bytes` when Copout shortens an output, while XML adds the same attributes to `<output>`. This presentation truncation is separate from any truncation reported by Atuin. Because schema v9 uses one universal envelope, the presentation rules no longer depend on whether a command was selected with `-n 1`, a positional selector, or the TUI.

## Execution context

Schema version 9 retains compact environment and repository context. The defaults are intended to provide useful development context without automatically exposing hostnames, remotes, arbitrary environment variables, or large diffs.

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

## Output format (schema version 9)

Schema v9 has one record shape for every capture. The root contains capture metadata plus a non-empty `runs` array; a single selected command is represented by a one-element `runs` array, exactly like one run within a larger selection. The schema no longer has `scope`, distinct command/history record types, or the old `history` summary object. Query intent is not encoded into the result shape.

Copout's internal record retains capture metadata. In schema v9, `output.text` is normalized, human-readable terminal text in every format. `captured_bytes` measures Atuin's retrieved snapshot **before** Copout normalization, while `presented_bytes` measures the normalized text **after** optional output budgeting. `observed_bytes` is upstream PTY traffic, including redraws and control sequences; it is **not** directly comparable with the retained snapshot length. `total_bytes` is reserved for a verified complete-output byte count and remains unknown unless the provider supplies it. The Atuin output RPC's stored-rendered-output size is not a complete transcript size.

`completeness` is `unknown` for ordinary Atuin snapshots, `incomplete` when upstream truncation or a known incomplete exit capture is reported, and `unavailable` when there is no captured text. Atuin's `truncated: false` **does not establish that the entire terminal transcript is present**. A large difference between `observed_bytes` and snapshot bytes adds `coverage_warning: "rendered-snapshot-much-smaller-than-pty-traffic"`; that is a diagnostic indicator, **not proof** of dropped output. Copout cannot correct upstream snapshot loss by changing its own output budget.

A typical XML history result can look like:

```xml
<copout version="8" captured_at="2026-10-01T09:31:00-04:00">
  <environment login_shell="/bin/zsh" os="macos" arch="arm64" session_id="...">
    <python executable="/repo/.venv/bin/python" version="3.14.0" implementation="cpython" environment="/repo/.venv"/>
  </environment>
  <run history_id="..." status="0" cwd="/repo" duration_ms="102" recorded_at="2026-10-01 09:30:59">
    <git observed_at_capture="true" root="/repo" branch="main" detached="false" commit="abc123..." dirty="false"/>
    <command><![CDATA[printf 'hello\n']]></command>
    <output completeness="unknown"><![CDATA[hello]]></output>
  </run>
</copout>
```

XML has one `<run>` per selected command, including for a one-command capture, and every run carries its Atuin `history_id`. It does not repeat the run count as a root attribute. Run durations are canonical integer milliseconds in `duration_ms`. `captured_at` records when Copout built the record, while `recorded_at` is the timestamp supplied by Atuin for the command. Structured optional context uses child elements: extended Git context may add worktree attributes plus `<changed-file>` and `<diff>`, while explicitly requested environment variables and executable resolutions appear as `<variable>` and `<executable>` children of `<environment>`.

### Text encoding contract

When an element has no `encoding` attribute, its XML character content is the presented UTF-8 text directly. CDATA is only an XML serialization detail; ordinary XML parsing recovers the text.

When an element has `encoding="json-string"`, concatenate/read its XML character content and JSON-decode it exactly once to recover the presented text. This fallback is primarily needed for commands and metadata containing XML-forbidden characters; normal output has already been converted to safe plain text. Attribute values that need the same treatment use a companion marker such as `cwd_encoding="json-string"`.

"Presented text" means the text after Copout's terminal-end whitespace removal and any documented presentation truncation. It is therefore not necessarily byte-for-byte identical to the original PTY capture.

### Sparse output metadata

An ordinary captured snapshot remains compact:

```xml
<output><![CDATA[hello]]></output>
```

Capture completeness is explicit. Other extended attributes appear when they explain an exceptional capture or presentation limit. Supported attributes are:

- `state`: emitted when output is not in the normal captured state, currently `state="unavailable"`.
- `encoding`: emitted only when the element payload is a JSON string rather than literal XML character content.
- `completeness`: always present on captured XML output; `unknown` is normal for a terminal snapshot, not a certification of completeness.
- `coverage_warning`: emitted when upstream PTY traffic is much larger than the rendered snapshot; this is a heuristic and does not prove loss.
- `truncated`: emitted as `true` when the upstream capture mechanism reports truncation.
- `captured_bytes`: byte length of Atuin's retrieved snapshot before normalization. Shown in XML only with extended metadata.
- `presented_bytes`: byte length of the visible, normalized output text after Copout's own budget. Shown in XML only with extended metadata.
- `observed_bytes`: upstream count of bytes observed by the capture mechanism before rendering, when supplied and extended metadata is needed.
- `total_bytes`: true complete-output byte size, only when a backend can supply that fact independently. Copout does not infer it, and the current Atuin RPC's stored-rendered-output byte count is not used for this field.
- `exit_capture_complete`: whether the capture mechanism reports that capture remained active through process termination. Copout emits it only when the upstream API provides it and extended metadata is otherwise relevant; absence does not imply `true`.

Copout also retains `presentation_truncated` and `presentation_omitted_bytes` when Copout itself shortens output to fit its presentation budget. That condition is independent of upstream `truncated`.

Unavailable output retains an `error` attribute when Copout knows why retrieval failed. Atuin-truncated output and Copout presentation truncation remain distinct.

Atuin's command capture is a terminal-rendered representation. Copout consumes that representation and does not intercept the underlying PTY stream, retain its own logs, or guarantee that rendered scrollback is available.

Daemon connection establishment, individual output requests, and status requests each have a three-second deadline. An unavailable or timed-out output request leaves usable history with output marked unavailable. A timed-out status request is reported by `copout doctor` and `copout verify`.

If output retrieval fails, the output record's `error` field (or XML attribute) preserves the reason. `UNIMPLEMENTED` means the daemon does not provide the output RPC expected by the installed Jerakeen client; it is not evidence of a missing capture or a disabled configuration flag. A healthy daemon status alone does not establish output API compatibility. `copout doctor` and `copout verify` report this distinction.


## Collecting capture-fidelity evidence

To reproduce a bounded but long terminal transcript, run `bash scripts/probe_output.sh` in a Kitty shell with Atuin output capture active. Alternatively, run the command you actually want to diagnose. Optionally select its visible output in Kitty and copy it to the clipboard. Then, from this repository in the same Atuin session:

```console
uv run python scripts/collect_evidence.py --kitty-clipboard
```

Omit `--kitty-clipboard` if there is no Kitty selection to save. The collector skips its own shell-history entry and retrieves the most recent other eligible command via Atuin/Jerakeen. It writes one timestamped directory with `copout.json`, `copout.xml`, `copout.md`, and `summary.json`; with the optional clipboard input it also saves `kitty-selection.txt` and `kitty-vs-copout.diff`. The comparison is diagnostic, not a byte-for-byte PTY equivalence test: Kitty selection may include prompts, and Atuin collapses redrawn output.

Use `--history-id ID` to select an exact history entry within the latest 100 entries, or `--output DIRECTORY` to control the new evidence directory. Evidence may contain sensitive terminal text; inspect it before sharing.

## Testing

Run `just check` for non-mutating lint, formatting, typing, and the test suite. `just repair` syncs dependencies, applies formatting and safe Ruff fixes, then runs type checking and tests without redundantly rerunning the Ruff validation passes. Add `--unsafe-fixes` to `just repair` or `just lint` to enable Ruff's unsafe fixes.

Command tests execute the installed `copout` launcher and module entry point in subprocesses with a controlled Atuin executable, Jerakeen client, clipboard helper, and isolated config directory. They cover root selector dispatch, direct and preselected selection, normalized output, unavailable output, service errors, diagnostics, clipboard delivery, context configuration, rendering, and selector window expansion without modifying the user's clipboard or history. The inline picker has headless Textual interaction tests for arrow and Vim navigation, multi-selection, confirmation, preselection, and cancellation.

The real shell capture tests are self-contained. When `zsh` and `atuin` are available, pytest starts an interactive zsh in a PTY, lets the normal Atuin shell integration initialize, executes standalone probes, waits across command boundaries for Atuin to finalize them, then verifies that Copout can retrieve the captured output. The stderr matrix covers shell builtins, short-lived child processes, direct fd-2 writes, buffered multi-chunk stderr, nonzero exits, missing final newlines, redirected stdout, pipelines, mixed stdout/stderr ordering, and rapid independent commands. Each probe also records what actually appeared on the child PTY, so a failure can distinguish a command that never emitted its sentinel from output that reached the terminal but disappeared before Copout retrieved it.

The rapid stderr probe count defaults to 16 and can be increased for reproduction runs, for example `COPOUT_STDERR_STRESS_COUNT=200 uv run pytest tests/test_live.py -k stderr -vv`. Live tests skip only when the required shell/Atuin executable is unavailable.
