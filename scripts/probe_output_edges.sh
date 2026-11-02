#!/usr/bin/env bash
# Run each case as a separate command in the same Atuin-enabled shell.
set -euo pipefail

case "${1:-}" in
  short)
    printf '%s\n' '__COPOUT_EDGE_SHORT_BEGIN__' \
      'On branch feature/edge-probe' 'working tree clean' \
      '__COPOUT_EDGE_SHORT_END__'
    ;;
  redraw)
    printf '%s\n' '__COPOUT_EDGE_REDRAW_BEGIN__'
    printf 'download 100%%\rready\033[K\n'
    printf '%s\n' '__COPOUT_EDGE_REDRAW_END__'
    ;;
  tail)
    printf '%s\n' '__COPOUT_EDGE_TAIL_BEGIN__'
    printf '%s\n' 'tail-flushed-before-exit'
    printf '%s\n' '__COPOUT_EDGE_TAIL_END__'
    exit 0
    ;;
  rapid-a)
    printf '%s\n' '__COPOUT_EDGE_RAPID_A_BEGIN__' \
      'rapid-first' '__COPOUT_EDGE_RAPID_A_END__'
    ;;
  rapid-b)
    printf '%s\n' '__COPOUT_EDGE_RAPID_B_BEGIN__' \
      'rapid-second' '__COPOUT_EDGE_RAPID_B_END__'
    ;;
  *)
    printf 'usage: bash scripts/probe_output_edges.sh {short|redraw|tail|rapid-a|rapid-b}\n' >&2
    exit 2
    ;;
esac
