#!/usr/bin/env python3
"""Benchmark multi-run Copout context enrichment against --no-context.

Requires a live Atuin session with N recorded commands. No output is persisted.
Measures complete CLI round trips, not just Git subprocess time; alternating
paired trials and exact history-ID checks reduce cache and selection bias.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path


def percentile(samples: list[float], fraction: float) -> float:
    """Nearest-rank percentile of samples in seconds."""
    if not samples:
        raise ValueError("samples cannot be empty")
    ordered = sorted(samples)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))]


def measure(*, count: int, context: bool) -> tuple[float, tuple[str, ...]]:
    command = [
        sys.executable, "-m", "copout.cli",
        "--print", "--json", "--last", str(count),
    ]
    if not context:
        command.append("--no-context")
    start = time.perf_counter()
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=60, check=False
    )
    elapsed = time.perf_counter() - start
    if result.returncode:
        raise RuntimeError(f"Copout failed ({result.returncode}): {result.stderr.strip()}")
    document = json.loads(result.stdout)
    ids = tuple(run["history_id"] for run in document["runs"])
    if len(ids) != count:
        raise RuntimeError(f"Expected {count} history entries, received {len(ids)}")
    return elapsed, ids


def benchmark(*, count: int, warmups: int, pairs: int) -> dict[str, object]:
    samples: dict[str, list[float]] = {"no_context": [], "context": []}
    expected_ids: tuple[str, ...] | None = None
    for index in range(warmups + pairs):
        # Alternate order: context first for odd pairs, otherwise control first.
        order = (False, True) if index % 2 == 0 else (True, False)
        for enabled in order:
            elapsed, ids = measure(count=count, context=enabled)
            if expected_ids is None:
                expected_ids = ids
            elif ids != expected_ids:
                raise RuntimeError("Atuin history selection changed during benchmark")
            if index >= warmups:
                samples["context" if enabled else "no_context"].append(elapsed)

    base = statistics.median(samples["no_context"])
    with_context = statistics.median(samples["context"])
    return {
        "history_count": count,
        "pairs": pairs,
        "warmup_pairs": warmups,
        "context_seconds": {
            "median": with_context,
            "p90": percentile(samples["context"], 0.9),
        },
        "no_context_seconds": {
            "median": base,
            "p90": percentile(samples["no_context"], 0.9),
        },
        "context_overhead_median_seconds": with_context - base,
        "context_overhead_median_ratio": with_context / base if base else None,
        "note": "Full CLI latency; compare on the same machine/session, not across hosts.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--pairs", type=int, default=10)
    parser.add_argument(
        "--json-output", type=Path, help="Optional report path (aggregate timings only)"
    )
    args = parser.parse_args()
    if args.count < 1 or args.warmups < 0 or args.pairs < 1:
        parser.error("requires count >= 1, warmups >= 0, and pairs >= 1")

    report = benchmark(count=args.count, warmups=args.warmups, pairs=args.pairs)
    rendered = json.dumps(report, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output is not None:
        args.json_output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
