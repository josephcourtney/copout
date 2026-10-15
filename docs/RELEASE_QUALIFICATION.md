# Copout 0.12.0 release qualification

Target: macOS with the user's real Kitty/zsh/Atuin 18.23.x integration and its pty-proxy. **Do not publish or tag on the strength of unit tests alone.** The program must not modify Atuin or shell configuration.

## Automated release gate

From a clean checkout of this candidate branch:

```console
bash scripts/qualify_release.sh
git status --short
```

The script runs a locked dependency sync, non-mutating `just check`, explicit live PTY tests with a skip guard, `just build`, and wheel/sdist structure and version inspections. It does not publish or tag. A missing dependency or skipped live test is an incomplete gate, not a pass.

## Human-observed Kitty interaction gate

Use a normal Kitty shell with a working Atuin session. First issue two recognizable commands, e.g. `printf 'copout-smoke-first\n'` and `printf 'copout-smoke-second\n'`. Then verify each:

- [ ] Bare `copout` opens the picker. With no selections, Enter copies the most recent eligible entry, without printing a second prompt or leaking TUI drawing into the payload.
- [ ] `copout` with Space on two entries and Enter copies two runs in chronological order. Esc cancels without replacing the clipboard.
- [ ] `copout --preselect 1,2` opens with the two selected. The relative numbers displayed refer to the same history records as `copout 1 2 -p --json`.
- [ ] `copout 1 2 --json -p`, `copout 2-3 --markdown -p`, and `copout --json -p -n 2` select the intended runs without entering the TUI.
- [ ] `copout -p > /tmp/copout-qualification-output.xml` opens the picker on the controlling tty and places only parseable XML on redirected stdout after Enter. Check with `python3 -c 'import xml.etree.ElementTree as e; e.parse("/tmp/copout-qualification-output.xml")'`. Remove the temporary file.
- [ ] Without a controlling terminal, bare `copout -p` exits nonzero with a useful message; explicit selectors still run headlessly. Use the following isolated-process check:

```console
python3 - <<'PY'
import subprocess
bad = subprocess.run(
    ["copout", "-p"],
    stdin=subprocess.DEVNULL, capture_output=True, text=True,
    start_new_session=True, check=False,
)
assert bad.returncode != 0, bad.stdout
good = subprocess.run(
    ["copout", "1", "-p", "--json"],
    stdin=subprocess.DEVNULL, capture_output=True, text=True,
    start_new_session=True, check=False,
)
assert good.returncode == 0, good.stderr
print("TTY behavior checked")
PY
```

## Terminal-capture fidelity gate

```console
bash scripts/probe_output.sh
# Select and copy the visible probe output in Kitty, then:
uv run python scripts/collect_evidence.py --kitty-clipboard
```

Examine the generated `summary.json`, `kitty-vs-atuin.diff`, and `kitty-vs-copout.diff`. Expect all 2,400 numbered probe lines in Atuin and Copout, with no Copout presentation truncation. Exact Kitty equality requires copying only the probe output without shell prompts or padding; if that selection differs, inspect the diff before diagnosing data loss.

Repeat with the **original Kev playground workload** or another real command that previously exposed capture fidelity problems. Unlike the synthetic probe, large interactive output may redraw or exceed the bounded presentation limit. Distinguish missing upstream data from intentional Copout omission using `presentation_truncated` and both diffs.

The collector creates potentially sensitive local diagnostic files. They must not be committed or attached to a public issue without review.

## Release decision

Record the completed gates and their command output before tagging or publishing. Update `CHANGELOG.md` from candidate/unreleased to a dated release section only after those gates pass. A release tag and publication are separate, explicit actions; the script deliberately performs neither.

## Optional hardening disposition

- **Atuin test-history isolation:** preserve the current real interactive-shell integration for release confidence. A synthetic `ATUIN_SESSION` alone is not proof that initialization, daemon output, and teardown use the isolated session. Only adopt isolation after validating the full lifecycle on macOS.
- **Typer upper bound:** exercise the locked installed version through `just check` and the CLI smoke matrix. Do not invent an upper bound without identifying a real incompatible version or a tested compatibility range.
- **Context-capture performance:** compare identical multi-run selectors with and without read-only context on the same session after warming Atuin. For example `hyperfine --warmup 3 'copout -n 10 -p --json --no-context >/dev/null' 'copout -n 10 -p --json >/dev/null'` if `hyperfine` is installed. Optimize only on a measured, reproducible regression; this is not a correctness gate.
- **Historical state:** do not fabricate earlier Git, Python, or environment context from current state. Introduce historical fields only when a trusted upstream source supplies them.
