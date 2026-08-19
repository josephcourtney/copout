from __future__ import annotations

import html
import json
from typing import Any


def _xml_text(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _cdata(value: object) -> str:
    text = "" if value is None else str(value)
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]] >".replace(" ", "")


def _mapping_value(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def _list_value(mapping: dict[str, Any], key: str) -> list[Any]:
    value = mapping.get(key)
    return value if isinstance(value, list) else []


def _render_run(run: dict[str, Any], indent: str = "  ") -> list[str]:
    result = _mapping_value(run, "result")
    output = _mapping_value(run, "output")
    context = _mapping_value(run, "context")
    timing = _mapping_value(run, "timing")
    attrs = [f'history_id="{_xml_text(run.get("history_id"))}"']
    if result.get("status") is not None:
        attrs.append(f'status="{_xml_text(result.get("status"))}"')
    if context.get("cwd"):
        attrs.append(f'cwd="{_xml_text(context.get("cwd"))}"')
    if timing.get("duration") is not None:
        attrs.append(f'duration="{_xml_text(timing.get("duration"))}"')
    lines = [f"{indent}<run {' '.join(attrs)}>"]
    lines.append(f"{indent}  <command>{_cdata(run.get('command'))}</command>")
    lines.append(
        f'{indent}  <output state="{_xml_text(output.get("state"))}" source="{_xml_text(output.get("source"))}">{_cdata(output.get("text"))}</output>'
    )
    lines.append(f"{indent}</run>")
    return lines


def render(record: dict[str, Any], *, as_json: bool = False, verbose: bool = False) -> str:
    del verbose
    if as_json:
        return json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if record.get("scope") == "history":
        history = _mapping_value(record, "history")
        lines = [
            f'<copout version="{_xml_text(record.get("version"))}" source="atuin" selected="{_xml_text(history.get("selected"))}">'
        ]
        runs = _list_value(record, "runs")
        for run in runs:
            if isinstance(run, dict):
                lines.extend(_render_run(run))
        lines.append("</copout>")
        return "\n".join(lines) + "\n"
    lines = [f'<copout version="{_xml_text(record.get("version"))}" source="atuin">']
    lines.extend(_render_run(record))
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
