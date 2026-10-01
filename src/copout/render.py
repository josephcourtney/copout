from __future__ import annotations

import copy
import html
import json
import re

from .context import EnvironmentContext, GitContext
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
    return round(seconds * 1000)


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


def _render_environment(
    environment: EnvironmentContext,
    *,
    pretty_attributes: bool,
) -> list[str]:
    scalar_names = (
        "login_shell",
        "shell_version",
        "os",
        "os_version",
        "arch",
        "hostname",
        "session_id",
    )
    attrs = [_attribute(name, environment[name]) for name in scalar_names if name in environment]
    children: list[str] = []

    if python_context := environment.get("python"):
        python_attrs = [_attribute(name, value) for name, value in python_context.items()]
        children.append(
            _opening_tag(
                "python",
                python_attrs,
                indent="    ",
                pretty_attributes=pretty_attributes,
            )[:-1]
            + "/>"
        )

    for name, value in environment.get("env", {}).items():
        children.append(
            _opening_tag(
                "variable",
                [_attribute("name", name), _attribute("value", value)],
                indent="    ",
                pretty_attributes=pretty_attributes,
            )[:-1]
            + "/>"
        )

    for name, path in environment.get("executables", {}).items():
        children.append(
            _opening_tag(
                "executable",
                [_attribute("name", name), _attribute("path", path)],
                indent="    ",
                pretty_attributes=pretty_attributes,
            )[:-1]
            + "/>"
        )

    opening = _opening_tag(
        "environment",
        attrs,
        indent="  ",
        pretty_attributes=pretty_attributes,
    )
    if not children:
        return [opening[:-1] + "/>" ]
    return [opening, *children, "  </environment>"]


def _render_git(git: GitContext, *, indent: str, pretty_attributes: bool) -> list[str]:
    scalar_names = (
        "observed_at_capture",
        "root",
        "branch",
        "detached",
        "commit",
        "dirty",
        "upstream",
        "ahead",
        "behind",
        "remote_url",
        "diff_truncated",
    )
    attrs: list[str] = []
    for name in scalar_names:
        if name not in git:
            continue
        value = git[name]
        if isinstance(value, bool):
            value = str(value).lower()
        attrs.append(_attribute(name, value))

    children = [
        _element("changed-file", path, indent=f"{indent}  ", pretty_attributes=pretty_attributes)
        for path in git.get("changed_files", [])
    ]
    if "diff" in git:
        children.append(
            _element("diff", git["diff"], indent=f"{indent}  ", pretty_attributes=pretty_attributes)
        )

    opening = _opening_tag("git", attrs, indent=indent, pretty_attributes=pretty_attributes)
    if not children:
        return [opening[:-1] + "/>" ]
    return [opening, *children, f"{indent}</git>"]


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
    if git := run["context"].get("git"):
        lines.extend(
            _render_git(git, indent=f"{indent}  ", pretty_attributes=pretty_attributes)
        )
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


def _fence(text: str, language: str = "") -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}{language}\n{text}\n{marker}"


def _inline_value(value: str) -> str:
    quoted = json.dumps(value, ensure_ascii=True)
    longest = max((len(match.group()) for match in re.finditer(r"`+", quoted)), default=0)
    marker = "`" * (longest + 1)
    return f"{marker}{quoted}{marker}"


def _markdown_environment(environment: EnvironmentContext) -> list[str]:
    details: list[str] = []
    for name in ("os", "arch", "login_shell", "hostname", "session_id"):
        if value := environment.get(name):
            details.append(f"{name} {_inline_value(str(value))}")
    if python_context := environment.get("python"):
        details.append(f"python {_inline_value(python_context.get('version', ''))}")
    return details


def _render_markdown(record: CopoutRecord) -> str:
    lines: list[str] = []
    if environment := record.get("environment"):
        details = _markdown_environment(environment)
        if details:
            lines.extend(("### Environment", "", " · ".join(details), ""))

    for index, run in enumerate(_record_runs(record), start=1):
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"### Run {index}" if record["scope"] == "history" else "### Command")
        details: list[str] = []
        if (status := run["result"]["status"]) is not None:
            details.append(f"exit {status}")
        if cwd := run["context"]["cwd"]:
            details.append(f"cwd {_inline_value(cwd)}")
        if (duration := run["timing"]["duration"]) is not None:
            details.append(f"{_duration_ms(duration)} ms")
        if git := run["context"].get("git"):
            if branch := git.get("branch"):
                details.append(f"git {_inline_value(branch)}")
            if commit := git.get("commit"):
                details.append(f"commit {_inline_value(commit[:12])}")
            if git.get("dirty"):
                details.append("dirty")
        if details:
            lines.extend(("", " · ".join(details)))
        lines.extend(("", "Command:", "", _fence(run["command"], "console")))
        output = run["output"]
        if output["state"] == "captured":
            lines.extend(("", "Output:", "", _fence(output["text"])))
        else:
            lines.extend(("", "Output unavailable."))
        if output["truncated"]:
            lines.extend(("", "Note: Atuin truncated the captured output."))
        if output.get("presentation_truncated"):
            omitted = output.get("presentation_omitted_bytes", 0)
            lines.extend(("", f"Note: Copout omitted {omitted} output bytes."))
        if output["error"]:
            lines.extend(("", f"Output retrieval error: {_inline_value(output['error'])}"))
    return "\n".join(lines) + "\n"


def render(
    record: CopoutRecord,
    *,
    as_json: bool = False,
    as_markdown: bool = False,
    pretty_attributes: bool = False,
) -> str:
    projected = _semantic_record(record)
    if as_markdown:
        return _render_markdown(projected)
    if as_json:
        return json.dumps(projected, indent=2, ensure_ascii=False) + "\n"

    attrs = [_attribute("version", projected["version"])]
    include_history_id = projected["scope"] == "history"
    runs = _record_runs(projected)

    lines = [
        _opening_tag(
            "copout",
            attrs,
            pretty_attributes=pretty_attributes,
        )
    ]
    if environment := projected.get("environment"):
        lines.extend(_render_environment(environment, pretty_attributes=pretty_attributes))
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
