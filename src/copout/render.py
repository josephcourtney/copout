from __future__ import annotations

import copy
import html
import json

from .record import CopoutRecord, RunRecord


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
    """Remove terminal-end ASCII whitespace while preserving internal layout and SGR styling."""
    return text.rstrip(" \t\r\n")


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
    include_history_id: bool,
    indent: str = "  ",
) -> list[str]:
    output = run["output"]
    attrs: list[str] = []

    if include_history_id:
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
    if output["state"] == "unavailable":
        output_attrs.append(_attribute("state", "unavailable"))
    if output["truncated"]:
        output_attrs.append(_attribute("truncated", "true"))
    if output["error"] is not None:
        output_attrs.append(_attribute("error", output["error"]))

    attr_text = f" {' '.join(output_attrs)}" if output_attrs else ""
    lines.append(f"{indent}  {_element('output', _semantic_text(output['text']), attr_text)}")
    lines.append(f"{indent}</run>")
    return lines


def render(record: CopoutRecord, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_semantic_record(record), indent=2, ensure_ascii=False) + "\n"

    attrs = [_attribute("version", record["version"])]
    runs: list[RunRecord]
    include_history_id = record["scope"] == "history"
    if record["scope"] == "history":
        attrs.append(_attribute("selected", record["history"]["selected"]))
        runs = record["runs"]
    else:
        runs = [record]

    lines = [f"<copout {' '.join(attrs)}>"]
    for run in runs:
        lines.extend(_render_run(run, include_history_id=include_history_id))
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
