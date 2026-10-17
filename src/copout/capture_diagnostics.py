"""Read-only diagnostics for one assembled Copout capture.

Upstream output is a terminal snapshot, not a proven transcript. An absence of
known defects therefore means "no detected issues", not "complete output".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from .record import CopoutRecord

Severity = Literal["error", "partial", "warning"]


@dataclass(frozen=True, slots=True)
class Issue:
    severity: Severity
    code: str
    run: int | None = None


@dataclass(frozen=True, slots=True)
class RunStats:
    index: int
    command_bytes: int
    command_lines: int
    captured_bytes: int
    presented_bytes: int
    presented_lines: int
    state: str
    completeness: str


@dataclass(frozen=True, slots=True)
class CaptureReport:
    requested: int | None
    runs: tuple[RunStats, ...]
    captured: int
    nonempty: int
    unavailable: int
    command_bytes: int
    captured_bytes: int
    presented_bytes: int
    omitted_bytes: int
    document_bytes: int
    issues: tuple[Issue, ...]

    @property
    def check_failed(self) -> bool:
        return any(issue.severity in ("error", "partial") for issue in self.issues)

    @property
    def status(self) -> str:
        if any(issue.severity == "error" for issue in self.issues):
            return "invalid"
        if any(issue.severity == "partial" for issue in self.issues):
            return "partial"
        return "no detected loss"  # Not a claim of complete upstream history.


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8", errors="surrogatepass"))


def _line_count(value: str) -> int:
    return len(value.splitlines())


def inspect(
    original: CopoutRecord,
    presented: CopoutRecord,
    document: str,
    *,
    requested: int | None = None,
    expected_ids: list[str] | None = None,
) -> CaptureReport:
    """Compare selected history, raw snapshots, projected text and final payload.

    'requested' is a selection count, not the size of all Atuin session history.
    'expected_ids' is available for picker/positional selection; never fabricate
    upstream coverage information for history queries that do not expose IDs.
    """
    original_runs = original["runs"]
    presented_runs = presented["runs"]
    issues: list[Issue] = []
    if requested is not None and len(original_runs) != requested:
        issues.append(Issue("partial", "selection-shortfall"))
    if len(original_runs) != len(presented_runs):
        issues.append(Issue("error", "projection-run-count-mismatch"))
    ids = [run["history_id"] for run in original_runs]
    if len(set(ids)) != len(ids):
        issues.append(Issue("error", "duplicate-history-id"))
    if expected_ids is not None and ids != expected_ids:
        issues.append(Issue("error", "selected-history-id-mismatch"))

    stats: list[RunStats] = []
    for index, (raw, shown) in enumerate(zip(original_runs, presented_runs), start=1):
        if raw["history_id"] != shown["history_id"] or raw["command"] != shown["command"]:
            issues.append(Issue("error", "projection-identity-mismatch", index))
        command = raw["command"]
        if not command:
            issues.append(Issue("error", "empty-command", index))
        source = raw["output"]
        output = shown["output"]
        raw_size = _utf8_size(source["text"])
        shown_size = _utf8_size(output["text"])
        if source["captured_bytes"] != raw_size:
            issues.append(Issue("error", "captured-byte-count-mismatch", index))
        if output["presented_bytes"] != shown_size:
            issues.append(Issue("error", "presented-byte-count-mismatch", index))
        if source["state"] != output["state"] or source["completeness"] != output["completeness"]:
            issues.append(Issue("error", "projection-state-mismatch", index))
        if source["state"] == "unavailable":
            if source["text"] or source["captured_bytes"]:
                issues.append(Issue("error", "unavailable-with-text", index))
            issues.append(Issue("partial", "output-unavailable", index))
        elif source["state"] != "captured":
            issues.append(Issue("error", "unknown-output-state", index))
        if source["completeness"] == "incomplete" or source["truncated"] is True:
            issues.append(Issue("partial", "upstream-incomplete", index))
        if source.get("exit_capture_complete") is False:
            # Do not double-count a known incomplete snapshot.
            if source["completeness"] != "incomplete" and source["truncated"] is not True:
                issues.append(Issue("partial", "upstream-incomplete", index))
        if output.get("presentation_truncated"):
            if output.get("presentation_omitted_bytes", 0) <= 0:
                issues.append(Issue("error", "invalid-omission-metadata", index))
            issues.append(Issue("partial", "presentation-truncated", index))
        elif output.get("presentation_omitted_bytes", 0):
            issues.append(Issue("error", "invalid-omission-metadata", index))
        if source.get("coverage_warning"):
            issues.append(Issue("warning", "upstream-coverage-suspected", index))
        if source.get("error") and source["state"] == "captured":
            issues.append(Issue("warning", "unexpected-output-error", index))
        stats.append(
            RunStats(
                index=index,
                command_bytes=_utf8_size(command),
                command_lines=_line_count(command),
                captured_bytes=raw_size,
                presented_bytes=shown_size,
                presented_lines=_line_count(output["text"]),
                state=source["state"],
                completeness=source["completeness"],
            )
        )

    return CaptureReport(
        requested=requested,
        runs=tuple(stats),
        captured=sum(item.state == "captured" for item in stats),
        nonempty=sum(item.state == "captured" and item.captured_bytes > 0 for item in stats),
        unavailable=sum(item.state == "unavailable" for item in stats),
        command_bytes=sum(item.command_bytes for item in stats),
        captured_bytes=sum(item.captured_bytes for item in stats),
        presented_bytes=sum(item.presented_bytes for item in stats),
        omitted_bytes=sum(
            run["output"].get("presentation_omitted_bytes", 0) for run in presented_runs
        ),
        document_bytes=_utf8_size(document),
        issues=tuple(issues),
    )


def format_report(report: CaptureReport, *, verbose: bool = False) -> str:
    """Format bounded, content-free diagnostics for stderr."""
    lines = [
        f"copout capture diagnostics: {report.status}",
        f"  commands: {len(report.runs)} assembled"
        + (f" / {report.requested} requested" if report.requested is not None else ""),
        f"  outputs: {report.captured} captured ({report.nonempty} nonempty), "
        f"{report.unavailable} unavailable",
        f"  bytes: commands={report.command_bytes}, raw-output={report.captured_bytes}, "
        f"presented-output={report.presented_bytes}, omitted={report.omitted_bytes}, "
        f"document={report.document_bytes}",
    ]
    counts = Counter((item.severity, item.code) for item in report.issues)
    if counts:
        for (severity, code), count in sorted(counts.items()):
            lines.append(f"  {severity}: {code} ({count})")
    else:
        lines.append("  findings: none (upstream completeness remains unverified)")
    if verbose:
        for run in report.runs:
            lines.append(
                f"  run {run.index}: command={run.command_bytes} bytes/"
                f"{run.command_lines} lines; output={run.captured_bytes} raw bytes/"
                f"{run.presented_bytes} presented bytes/{run.presented_lines} lines; "
                f"{run.state}, completeness={run.completeness}"
            )
        for issue in report.issues:
            if issue.run is not None:
                lines.append(f"    run {issue.run}: {issue.severity} {issue.code}")
    return "\n".join(lines) + "\n"
