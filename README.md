# Copout

Copout copies recent terminal history into the clipboard as compact XML or JSON. Atuin is the source of truth for command history and metadata; Atuin's daemon plus `pty-proxy` supply recent command output. Copout uses Atuin's documented history CLI for persisted session history and Jerakeen for direct daemon access to captured output.

Copout does **not** run a terminal watcher, maintain its own command journal, or modify shell or Atuin configuration.

## Requirements

- Python 3.13+
- Atuin 18.17+ on `PATH`
- Atuin shell integration
- For command output: Atuin daemon + `pty-proxy`
- macOS `pbcopy`, Wayland `wl-copy`, or X11 `xclip`/`xsel`

Atuin's captured output is intentionally recent and ephemeral: the daemon keeps recent output in memory and it disappears when the daemon stops. Command history and metadata remain available through Atuin.

## Setup

Configure Atuin itself for daemon-backed output capture:

```console
atuin config set daemon.enabled true
atuin config set daemon.autostart true
atuin config set pty_proxy.enabled true
```

Open a new shell afterward, run a command, then verify the complete path:

```console
false
copout verify
```

`copout doctor` is read-only. It reports missing configuration and prints the Atuin commands needed to correct it, but does not make changes itself.

## Use

```console
copout                 # previous non-copout command + captured output
copout -p              # print instead of clipboard
copout --json          # JSON instead of XML
copout -n 5            # last five commands in the current Atuin session
copout --failure       # most recent failed command
copout doctor          # detailed integration diagnostics
copout verify          # concise history + output assertion
```

Copout retrieves persisted chronological history with `atuin history list --session` and retrieves recent captured output from the Atuin daemon through Jerakeen. It does not access Atuin's private database or implement the daemon gRPC protocol itself.

## Testing

Run `just check` for lint, formatting, typing, and the test suite. Command tests execute the installed `copout` launcher and module entry point in subprocesses, with a controlled Atuin executable, Jerakeen client, and clipboard helper. They cover selection, captured and unavailable output, service errors, diagnostics, and clipboard delivery without modifying your clipboard or history.

The real shell capture test is opt-in. In an Atuin-integrated terminal with output capture enabled, run these as two separate commands:

```console
printf 'copout-live-probe\n'
```

Wait for the next shell prompt. Then run the test separately in that same terminal (do not paste both commands together):

```console
COPOUT_LIVE_ATUIN=1 .venv/bin/pytest -q tests/test_live.py
```

This checks that the real installed command retrieves the probe from the current session and returns its captured output. It fails if the probe is missing or output capture is unavailable. The ordinary suite skips this test; passing controlled command tests does not establish that your shell's Atuin capture is configured correctly.

## Output format (schema version 4)

JSON output retains the original command and captured text. Each output record includes `utf8_bytes` (the bytes returned in `text`), plus Atuin's `truncated`, `observed_bytes`, and `total_bytes` metadata. Unknown metadata is `null` in JSON and omitted from XML; unavailable output must not be interpreted as a complete empty capture.

XML normally uses readable CDATA. If text contains XML-invalid characters (including ANSI escape codes), or carriage returns that XML parsing would normalize, the element has `encoding="json-string"` and its CDATA contains a JSON string literal. Parse the XML, then JSON-decode that element's text to recover the original string. Attribute values that require this treatment have a companion marker such as `cwd_encoding="json-string"`; attribute tabs and newlines are encoded too. Consumers of version 3 must recognize these version 4 encoding markers before interpreting text. Characters are preserved rather than stripped.

Daemon connection establishment, individual output requests, and status requests each have a three-second deadline. An unavailable or timed-out output request leaves usable history with output marked unavailable. A timed-out status request is reported by `copout doctor` and `copout verify`.

If output retrieval fails, the output record's `error` field (or XML attribute) preserves the reason. `UNIMPLEMENTED` means the daemon does not provide the output RPC expected by the installed Jerakeen client; it is not evidence of a missing capture or a disabled configuration flag. A healthy daemon status alone does not establish output API compatibility. `copout doctor` and `copout verify` report this distinction.
