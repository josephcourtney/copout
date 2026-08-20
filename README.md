# Copout

Copout copies recent terminal history into the clipboard as compact XML or JSON. Atuin is the source of truth for command history and metadata; Atuin's daemon plus `pty-proxy` supply recent command output.

Copout does **not** run a terminal watcher and does not maintain its own command journal.

## Requirements

- Python 3.13+
- Atuin 18.17+ on `PATH`
- Atuin shell integration
- Jerakeen (installed as a Copout dependency)
- For command output: Atuin daemon + `pty-proxy`
- macOS `pbcopy`, Wayland `wl-copy`, or X11 `xclip`/`xsel`

Atuin's captured output is intentionally recent and ephemeral: the daemon keeps recent output in memory and it disappears when the daemon stops. Command history and metadata remain available through Atuin.

## Setup

```console
copout install
```

For zsh, bash, and fish this enables Atuin's daemon/autostart configuration and adds `pty-proxy` initialization before the normal `atuin init` line. Open a new shell afterward, then verify:

```console
false
copout verify
```

## Use

```console
copout                 # previous non-copout command + captured output
copout -p              # print instead of clipboard
copout --json          # JSON instead of XML
copout -n 5            # last five commands in the current Atuin session
copout --failure       # most recent failed command
copout doctor          # integration diagnostics
copout verify          # assert history + output capture work
```

## Integration boundary

Copout no longer starts or talks to `atuin mcp`.

Persisted command selection comes from Atuin's documented `atuin history list --session` interface. Captured output and daemon health come from Jerakeen's public Python API, which talks directly to the local Atuin daemon. This split preserves Copout's chronological "last N invocations" behavior without depending on Atuin's private database or daemon protocol.
