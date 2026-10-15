"""Offline checks for opt-in hardening scripts (no network or real Atuin required)."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_context_benchmark_nearest_rank_percentiles() -> None:
    namespace = run_path(str(ROOT / "scripts" / "benchmark_context.py"))
    percentile = namespace["percentile"]
    assert percentile([0.4, 0.1, 0.3, 0.2], 0.9) == 0.4
    assert percentile([0.4, 0.1, 0.3, 0.2], 0.5) == 0.2
    with pytest.raises(ValueError, match="cannot be empty"):
        percentile([], 0.9)


def test_context_benchmark_checks_stable_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = run_path(str(ROOT / "scripts" / "benchmark_context.py"))
    benchmark = namespace["benchmark"]
    calls: list[bool] = []

    def fake_measure(*, count: int, context: bool) -> tuple[float, tuple[str, ...]]:
        assert count == 3
        calls.append(context)
        return (1.0 if context else 0.5, ("a", "b", "c"))

    monkeypatch.setitem(benchmark.__globals__, "measure", fake_measure)
    report = benchmark(count=3, warmups=1, pairs=2)
    assert len(calls) == 6
    assert report["context_overhead_median_seconds"] == 0.5
    assert report["context_overhead_median_ratio"] == 2.0

    def drifting_measure(*, count: int, context: bool) -> tuple[float, tuple[str, ...]]:
        return (0.1, ("a", "b", "c") if context else ("x", "b", "c"))

    monkeypatch.setitem(benchmark.__globals__, "measure", drifting_measure)
    with pytest.raises(RuntimeError, match="selection changed"):
        benchmark(count=3, warmups=0, pairs=1)


def test_typer_matrix_spans_click_vendor_boundary() -> None:
    namespace = run_path(str(ROOT / "scripts" / "check_typer_compatibility.py"))
    versions = namespace["DEFAULT_VERSIONS"]
    assert "0.24.1" in versions
    assert "0.26.0" in versions
    assert "0.27.2" in versions
