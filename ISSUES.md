# Known issues

## Unconfirmed / unreproduced

- [ ] **Intermittent stderr output may sometimes be absent from a captured command.** This has been observed during normal use but has not been reproduced under controlled testing. Real zsh + Atuin + pty-proxy coverage now verifies stderr from shell builtins, short-lived child processes, direct fd 2 writes, buffered multi-chunk output, nonzero exits, pipelines, redirected stdout, missing final newlines, and mixed stdout/stderr ordering. Rapid-command stress runs at 200 and 1000 commands also passed without loss. No production workaround or capture change is currently justified. If the behavior recurs, preserve the exact command and context so the retained PTY-vs-Atuin diagnostics can localize the loss.

## Resolved CLI UX issues

- [x] Invoking `copout` without an explicit selection query opens the TUI by default.
- [x] Positional selectors such as `copout 1`, `copout 1 3`, `copout 2-5`, and comma-separated combinations gather exactly those history entries without opening the TUI.
- [x] `--preselect` keeps relative-position preselection available when opening the TUI, while `--preselect-records` preserves stable Atuin-record preselection for integrations.
- [x] Explicit selectors automatically extend history discovery beyond the TUI's default browse window when necessary.
- [x] The TUI accepts Vim-style navigation keys (`j`/`k`, `g`/`G`, `Ctrl-D`/`Ctrl-U`) in addition to the existing navigation keys.
