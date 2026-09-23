from __future__ import annotations

import copy
import html
import json
from typing import Literal

from .record import CopoutRecord, RunRecord

type OutputMode = Literal["semantic", "rendered"]


def _encoded_text(text: str, *, attribute: bool = False) -> tuple[str, bool]:
    # XML 1.0 excludes most controls, surrogates, U+FFFE and U+FFFF.
    # XML parsing also normalizes CRs and attribute whitespace.
    needs_encoding = any(
        not (
            char in "\t\n"
            or " " <= char <= "\ud7ff"
            or "\ue000" <= char <= "\ufffd"
            or "\U00010000" <= char <= "\U0010ffff"
        )
        or (attribute and char in "\t\n")
        for char in text
    )
    return (json.dumps(text, ensure_ascii=True), True) if needs_encoding else (text, False)


def _attribute(name: str, value: str | int | float) -> str:
    text, encoded = _encoded_text(str(value), attribute=True)
    marker = f' {name}_encoding="json-string"' if encoded else ""
    return f'{name}="{html.escape(text)}"{marker}'


def _element(name: str, text: str, attrs: str = "") -> str:
    text, encoded = _encoded_text(text)
    marker = ' encoding="json-string"' if encoded else ""
    cdata = text.replace("]]>", "]]]]><![CDATA[>")
    return f"<{name}{attrs}{marker}><![CDATA[{cdata}]]></{name}>"


def _semantic_text(text: str) -> str:
    """Remove terminal-end whitespace while preserving internal layout."""
    return text.rstrip()


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.6g}ms"
    return f"{seconds:.6g}s"


def _record_runs(record: CopoutRecord) -> list[RunRecord]:
    if record["scope"] == "history":
        return record["runs"]
    return [record]


def _semantic_record(record: CopoutRecord) -> CopoutRecord:
    projected = copy.deepcopy(record)
    for run in _record_runs(projected):
        output = run["output"]
        text = _semantic_text(output["text"])
        output["text"] = text
        output["utf8_bytes"] = len(text.encode())
    return projected


def _render_run(
    run: RunRecord,
    *,
    mode: OutputMode,
    include_history_id: bool,
    indent: str = "  ",
) -> list[str]:
    output = run["output"]
    attrs: list[str] = []

    if mode == "rendered" or include_history_id:
        attrs.append(_attribute("history_id", run["history_id"]))
    if (status := run["result"]["status"]) is not None:
        attrs.append(_attribute("status", status))
    if cwd := run["context"]["cwd"]:
        attrs.append(_attribute("cwd", cwd))
    if (duration := run["timing"]["duration"]) is not None:
        attrs.append(_attribute("duration", _format_duration(duration)))

    run_open = f"{indent}<run"
    if attrs:
        run_open += f" {' '.join(attrs)}"
    run_open += ">"
    lines = [run_open]
    lines.append(f"{indent}  {_element('command', run['command'])}")

    output_attrs: list[str] = []
    if mode == "rendered":
        output_attrs.extend(
            (
                _attribute("state", output["state"]),
                _attribute("source", output["source"]),
                _attribute("utf8_bytes", output["utf8_bytes"]),
            )
        )
        if output["error"] is not None:
            output_attrs.append(_attribute("error", output["error"]))
        for key in ("truncated", "observed_bytes", "total_bytes"):
            value = output[key]
            if value is not None:
                output_attrs.append(
                    _attribute(key, str(value).lower() if isinstance(value, bool) else value)
                )
        text = output["text"]
    else:
        if output["state"] == "unavailable":
            output_attrs.append(_attribute("state", "unavailable"))
        if output["truncated"]:
            output_attrs.append(_attribute("truncated", "true"))
        if output["error"] is not None:
            output_attrs.append(_attribute("error", output["error"]))
        text = _semantic_text(output["text"])

    attr_text = f" {' '.join(output_attrs)}" if output_attrs else ""
    lines.append(f"{indent}  {_element('output', text, attr_text)}")
    lines.append(f"{indent}</run>")
    return lines


def render(
    record: CopoutRecord,
    *,
    as_json: bool = False,
    mode: OutputMode = "semantic",
) -> str:
    if as_json:
        payload = record if mode == "rendered" else _semantic_record(record)
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    attrs = [_attribute("version", record["version"])]
    if mode == "rendered":
        attrs.append(_attribute("source", record["source"]))

    runs: list[RunRecord]
    include_history_id = record["scope"] == "history"
    if record["scope"] == "history":
        attrs.append(_attribute("selected", record["history"]["selected"]))
        runs = record["runs"]
    else:
        runs = [record]

    lines = [f"<copout {' '.join(attrs)}>"]
    for run in runs:
        lines.extend(
            _render_run(
                run,
                mode=mode,
                include_history_id=include_history_id,
            )
        )
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
