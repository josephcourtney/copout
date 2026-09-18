from __future__ import annotations

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


def _render_run(run: RunRecord, indent: str = "  ") -> list[str]:
    output = run["output"]
    attrs = [_attribute("history_id", run["history_id"])]

    if (status := run["result"]["status"]) is not None:
        attrs.append(_attribute("status", status))
    if cwd := run["context"]["cwd"]:
        attrs.append(_attribute("cwd", cwd))
    if (duration := run["timing"]["duration"]) is not None:
        attrs.append(_attribute("duration", duration))

    lines = [f"{indent}<run {' '.join(attrs)}>"]
    lines.append(f"{indent}  {_element('command', run['command'])}")
    output_attrs = [
        _attribute("state", output["state"]),
        _attribute("source", output["source"]),
        _attribute("utf8_bytes", output["utf8_bytes"]),
    ]
    if output["error"] is not None:
        output_attrs.append(_attribute("error", output["error"]))
    for key in ("truncated", "observed_bytes", "total_bytes"):
        value = output[key]
        if value is not None:
            output_attrs.append(
                _attribute(key, str(value).lower() if isinstance(value, bool) else value)
            )
    lines.append(f"{indent}  {_element('output', output['text'], ' ' + ' '.join(output_attrs))}")
    lines.append(f"{indent}</run>")
    return lines


def render(record: CopoutRecord, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(record, indent=2, ensure_ascii=False) + "\n"

    attrs = [
        _attribute("version", record["version"]),
        _attribute("source", record["source"]),
    ]
    runs: list[RunRecord]
    if record["scope"] == "history":
        attrs.append(_attribute("selected", record["history"]["selected"]))
        runs = record["runs"]
    else:
        runs = [record]

    lines = [f"<copout {' '.join(attrs)}>"]
    for run in runs:
        lines.extend(_render_run(run))
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
