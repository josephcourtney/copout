# Resolved CLI UX issues

- [x] Invoking `copout` without an explicit selection query opens the TUI by default.
- [x] Positional selectors such as `copout 1`, `copout 1 3`, `copout 2-5`, and comma-separated combinations gather exactly those history entries without opening the TUI.
- [x] `--preselect` keeps relative-position preselection available when opening the TUI, while `--preselect-records` preserves stable Atuin-record preselection for integrations.
- [x] Explicit selectors automatically extend history discovery beyond the TUI's default browse window when necessary.
- [x] The TUI accepts Vim-style navigation keys (`j`/`k`, `g`/`G`, `Ctrl-D`/`Ctrl-U`) in addition to the existing navigation keys.
