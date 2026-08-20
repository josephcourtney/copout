from __future__ import annotations

import html
import json

from .record import CopoutRecord, RunRecord


def _xml_text(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _cdata(value: object) -> str:
    text = "" if value is None else str(value)
    return f"<![CDATA[{text.replace(']]>', ']]]]><![CDATA[>')}]]>"


def _render_run(run: RunRecord, indent: str = "  ") -> list[str]:
    output = run["output"]
    attrs = [f'history_id="{_xml_text(run["history_id"])}"']

    if (status := run["result"]["status"]) is not None:
        attrs.append(f'status="{_xml_text(status)}"')
    if cwd := run["context"]["cwd"]:
        attrs.append(f'cwd="{_xml_text(cwd)}"')
    if (duration := run["timing"]["duration"]) is not None:
        attrs.append(f'duration="{_xml_text(duration)}"')

    lines = [f"{indent}<run {' '.join(attrs)}>"]
    lines.append(f"{indent}  <command>{_cdata(run['command'])}</command>")
    lines.append(
        f'{indent}  <output state="{_xml_text(output["state"])}" '
        f'source="{_xml_text(output["source"])}">{_cdata(output["text"])}</output>'
    )
    lines.append(f"{indent}</run>")
    return lines


def render(record: CopoutRecord, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(record, indent=2, ensure_ascii=False) + "\n"

    attrs = [
        f'version="{_xml_text(record["version"])}"',
        f'source="{_xml_text(record["source"])}"',
    ]
    runs: list[RunRecord]
    if record["scope"] == "history":
        attrs.append(f'selected="{_xml_text(record["history"]["selected"])}"')
        runs = record["runs"]
    else:
        runs = [record]

    lines = [f"<copout {' '.join(attrs)}>"]
    for run in runs:
        lines.extend(_render_run(run))
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
