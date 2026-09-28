from __future__ import annotations

import copy
import html
import json

from .record import CopoutRecord, OutputRecord, RunRecord

MAX_OUTPUT_BYTES_PER_RUN = 128 * 1024
MAX_OUTPUT_BYTES_TOTAL = 512 * 1024


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


def _opening_tag(
    name: str,
    attrs: list[str],
    *,
    indent: str = "",
    pretty_attributes: bool = False,
) -> str:
    if not attrs:
        return f"{indent}<{name}>"
    if not pretty_attributes or len(attrs) == 1:
        return f"{indent}<{name} {' '.join(attrs)}>"

    continuation = f"{indent}  "
    lines = [f"{indent}<{name}"]
    lines.extend(f"{continuation}{attr}" for attr in attrs[:-1])
    lines.append(f"{continuation}{attrs[-1]}>")
    return "\n".join(lines)


def _element(
    name: str,
    text: str,
    attrs: list[str] | None = None,
    *,
    indent: str = "",
    pretty_attributes: bool = False,
) -> str:
    encoded_text, encoded = _encoded_text(text)
    element_attrs = list(attrs or [])
    if encoded:
        element_attrs.append(_attribute("encoding", "json-string"))
    cdata = encoded_text.replace("]]>", "]]]]><![CDATA[>")
    opening = _opening_tag(
        name,
        element_attrs,
        indent=indent,
        pretty_attributes=pretty_attributes,
    )
    return f"{opening}<![CDATA[{cdata}]]></{name}>"


def _semantic_text(text: str) -> str:
    """Remove terminal-end ASCII whitespace while preserving internal layout and SGR styling."""
    return text.rstrip(" \t\r\n")


def _duration_ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def _record_runs(record: CopoutRecord) -> list[RunRecord]:
    if record["scope"] == "history":
        return record["runs"]
    return [record]


def _fair_output_budgets(sizes: list[int]) -> list[int]:
    caps = [min(size, MAX_OUTPUT_BYTES_PER_RUN) for size in sizes]
    if sum(caps) <= MAX_OUTPUT_BYTES_TOTAL:
        return caps

    low = 0
    high = MAX_OUTPUT_BYTES_PER_RUN
    while low < high:
        midpoint = (low + high + 1) // 2
        if sum(min(cap, midpoint) for cap in caps) <= MAX_OUTPUT_BYTES_TOTAL:
            low = midpoint
        else:
            high = midpoint - 1
    return [min(cap, low) for cap in caps]


def _utf8_prefix(data: bytes, budget: int) -> str:
    return data[:budget].decode("utf-8", errors="ignore")


def _utf8_suffix(data: bytes, budget: int) -> str:
    if budget == 0:
        return ""
    return data[-budget:].decode("utf-8", errors="ignore")


def _bound_text(text: str, *, budget: int) -> tuple[str, int]:
    data = text.encode()
    if len(data) <= budget:
        return text, 0
    if budget <= 0:
        return "", len(data)

    placeholder = f"\n... [copout omitted {len(data)} UTF-8 bytes] ...\n"
    marker_bytes = len(placeholder.encode())
    if marker_bytes >= budget:
        return _utf8_prefix(placeholder.encode(), budget), len(data)

    content_budget = budget - marker_bytes
    head_budget = (content_budget + 1) // 2
    tail_budget = content_budget // 2
    head = _utf8_prefix(data, head_budget)
    tail = _utf8_suffix(data, tail_budget)
    kept_bytes = len(head.encode()) + len(tail.encode())
    omitted = len(data) - kept_bytes
    marker = f"\n... [copout omitted {omitted} UTF-8 bytes] ...\n"
    bounded = head + marker + tail

    # The placeholder uses the largest possible byte count, so the actual marker
    # cannot make the result exceed the requested budget.
    return bounded, omitted


def _semantic_record(record: CopoutRecord) -> CopoutRecord:
    projected = copy.deepcopy(record)
    runs = _record_runs(projected)
    for run in runs:
        output = run["output"]
        text = _semantic_text(output["text"])
        output["text"] = text
        output["captured_bytes"] = len(text.encode())

    if projected["scope"] == "history":
        budgets = _fair_output_budgets([run["output"]["captured_bytes"] for run in runs])
        for run, budget in zip(runs, budgets, strict=True):
            output = run["output"]
            text, omitted = _bound_text(output["text"], budget=budget)
            output["text"] = text
            output["captured_bytes"] = len(text.encode())
            if omitted:
                output["presentation_truncated"] = True
                output["presentation_omitted_bytes"] = omitted
    return projected


def _extended_output_metadata_needed(output: OutputRecord) -> bool:
    return bool(
        output["truncated"]
        or output.get("presentation_truncated")
        or output.get("exit_capture_complete") is False
    )


def _output_attributes(output: OutputRecord) -> list[str]:
    attrs: list[str] = []
    if output["state"] != "captured":
        attrs.append(_attribute("state", output["state"]))

    extended = _extended_output_metadata_needed(output)
    if output["truncated"]:
        attrs.append(_attribute("truncated", "true"))
    if extended and output["state"] == "captured":
        attrs.append(_attribute("captured_bytes", output["captured_bytes"]))
        if output["observed_bytes"] is not None:
            attrs.append(_attribute("observed_bytes", output["observed_bytes"]))
        if output["total_bytes"] is not None:
            attrs.append(_attribute("total_bytes", output["total_bytes"]))
        if (complete := output.get("exit_capture_complete")) is not None:
            attrs.append(_attribute("exit_capture_complete", str(complete).lower()))

    if output.get("presentation_truncated"):
        attrs.append(_attribute("presentation_truncated", "true"))
        attrs.append(
            _attribute("presentation_omitted_bytes", output.get("presentation_omitted_bytes", 0))
        )
    if output["error"] is not None:
        attrs.append(_attribute("error", output["error"]))
    return attrs


def _render_run(
    run: RunRecord,
    *,
    include_history_id: bool,
    pretty_attributes: bool,
    indent: str = "  ",
) -> list[str]:
    attrs: list[str] = []

    if include_history_id:
        attrs.append(_attribute("history_id", run["history_id"]))
    if (status := run["result"]["status"]) is not None:
        attrs.append(_attribute("status", status))
    if cwd := run["context"]["cwd"]:
        attrs.append(_attribute("cwd", cwd))
    if (duration := run["timing"]["duration"]) is not None:
        attrs.append(_attribute("duration_ms", _duration_ms(duration)))

    lines = _opening_tag(
        "run",
        attrs,
        indent=indent,
        pretty_attributes=pretty_attributes,
    ).splitlines()
    lines.append(
        _element(
            "command",
            run["command"],
            indent=f"{indent}  ",
            pretty_attributes=pretty_attributes,
        )
    )
    lines.extend(
        _element(
            "output",
            run["output"]["text"],
            _output_attributes(run["output"]),
            indent=f"{indent}  ",
            pretty_attributes=pretty_attributes,
        ).splitlines()
    )
    lines.append(f"{indent}</run>")
    return lines


def render(
    record: CopoutRecord,
    *,
    as_json: bool = False,
    pretty_attributes: bool = False,
) -> str:
    projected = _semantic_record(record)
    if as_json:
        return json.dumps(projected, indent=2, ensure_ascii=False) + "\n"

    attrs = [_attribute("version", projected["version"])]
    runs: list[RunRecord]
    include_history_id = projected["scope"] == "history"
    if projected["scope"] == "history":
        runs = projected["runs"]
    else:
        runs = [projected]

    lines = [
        _opening_tag(
            "copout",
            attrs,
            pretty_attributes=pretty_attributes,
        )
    ]
    for run in runs:
        lines.extend(
            _render_run(
                run,
                include_history_id=include_history_id,
                pretty_attributes=pretty_attributes,
            )
        )
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
