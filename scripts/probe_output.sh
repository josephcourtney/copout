#!/usr/bin/env bash
# Run this as a single command in a Kitty shell with Atuin output capture.
set -euo pipefail

printf '%s\n' '__COPOUT_PROBE_BEGIN__'
for ((i = 1; i <= 2400; i++)); do
  printf 'probe %04d %072d\n' "$i" "$i"
done
printf '%s\n' '__COPOUT_STDERR__' >&2
printf '\033[32mcolored\033[0m\n'
printf 'download 100%%\rready\033[K\n'
printf '%s\n' '__COPOUT_PROBE_END__'
