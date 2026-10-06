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
    return record["runs"]


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
    return head + marker + tail, omitted


def _semantic_record(record: CopoutRecord) -> CopoutRecord:
    projected = copy.deepcopy(record)
    runs = _record_runs(projected)
    for run in runs:
        output = run["output"]
        text = _semantic_text(output["text"])
        output["text"] = text
        output["captured_bytes"] = len(text.encode())

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


def _self_closing_tag(
    name: str,
    attrs: list[str],
    *,
    indent: str,
    pretty_attributes: bool,
) -> str:
    return _opening_tag(name, attrs, indent=indent, pretty_attributes=pretty_attributes)[:-1] + "/>"


def _render_environment(
    environment: EnvironmentContext,
    *,
    pretty_attributes: bool,
) -> list[str]:
    attrs: list[str] = []
    if (value := environment.get("login_shell")) is not None:
        attrs.append(_attribute("login_shell", value))
    if (value := environment.get("shell_version")) is not None:
        attrs.append(_attribute("shell_version", value))
    if (value := environment.get("os")) is not None:
        attrs.append(_attribute("os", value))
    if (value := environment.get("os_version")) is not None:
        attrs.append(_attribute("os_version", value))
    if (value := environment.get("arch")) is not None:
        attrs.append(_attribute("arch", value))
    if (value := environment.get("hostname")) is not None:
        attrs.append(_attribute("hostname", value))
    if (value := environment.get("session_id")) is not None:
        attrs.append(_attribute("session_id", value))

    children: list[str] = []
    if python_context := environment.get("python"):
        python_attrs: list[str] = []
        if (value := python_context.get("executable")) is not None:
            python_attrs.append(_attribute("executable", value))
        if (value := python_context.get("version")) is not None:
            python_attrs.append(_attribute("version", value))
        if (value := python_context.get("implementation")) is not None:
            python_attrs.append(_attribute("implementation", value))
        if (value := python_context.get("environment")) is not None:
            python_attrs.append(_attribute("environment", value))
        children.append(
            _self_closing_tag(
                "python",
                python_attrs,
                indent="    ",
                pretty_attributes=pretty_attributes,
            )
        )

    for name, value in environment.get("env", {}).items():
        children.append(
            _self_closing_tag(
                "variable",
                [_attribute("name", name), _attribute("value", value)],
                indent="    ",
                pretty_attributes=pretty_attributes,
            )
        )

    for name, path in environment.get("executables", {}).items():
        children.append(
            _self_closing_tag(
                "executable",
                [_attribute("name", name), _attribute("path", path)],
                indent="    ",
                pretty_attributes=pretty_attributes,
            )
        )

    if not children:
        return [
            _self_closing_tag(
                "environment",
                attrs,
                indent="  ",
                pretty_attributes=pretty_attributes,
            )
        ]
    return [
        _opening_tag(
            "environment",
            attrs,
            indent="  ",
            pretty_attributes=pretty_attributes,
        ),
        *children,
        "  </environment>",
    ]


def _render_git(git: GitContext, *, indent: str, pretty_attributes: bool) -> list[str]:
    attrs: list[str] = []
    if (value := git.get("observed_at_capture")) is not None:
        attrs.append(_attribute("observed_at_capture", str(value).lower()))
    if (value := git.get("root")) is not None:
        attrs.append(_attribute("root", value))
    if (value := git.get("branch")) is not None:
        attrs.append(_attribute("branch", value))
    if (value := git.get("detached")) is not None:
        attrs.append(_attribute("detached", str(value).lower()))
    if (value := git.get("commit")) is not None:
        attrs.append(_attribute("commit", value))
    if (value := git.get("dirty")) is not None:
        attrs.append(_attribute("dirty", str(value).lower()))
    if (value := git.get("git_dir")) is not None:
        attrs.append(_attribute("git_dir", value))
    if (value := git.get("common_dir")) is not None:
        attrs.append(_attribute("common_dir", value))
    if (value := git.get("linked_worktree")) is not None:
        attrs.append(_attribute("linked_worktree", str(value).lower()))
    if (value := git.get("upstream")) is not None:
        attrs.append(_attribute("upstream", value))
    if (value := git.get("ahead")) is not None:
        attrs.append(_attribute("ahead", value))
    if (value := git.get("behind")) is not None:
        attrs.append(_attribute("behind", value))
    if (value := git.get("remote_url")) is not None:
        attrs.append(_attribute("remote_url", value))
    if (value := git.get("diff_truncated")) is not None:
        attrs.append(_attribute("diff_truncated", str(value).lower()))

    children = [
        _element("changed-file", path, indent=f"{indent}  ", pretty_attributes=pretty_attributes)
        for path in git.get("changed_files", [])
    ]
    if (diff := git.get("diff")) is not None:
        children.append(
            _element("diff", diff, indent=f"{indent}  ", pretty_attributes=pretty_attributes)
        )

    if not children:
        return [
            _self_closing_tag(
                "git",
                attrs,
                indent=indent,
                pretty_attributes=pretty_attributes,
            )
        ]
    return [
        _opening_tag("git", attrs, indent=indent, pretty_attributes=pretty_attributes),
        *children,
        f"{indent}</git>",
    ]


def _render_run(
    run: RunRecord,
    *,
    pretty_attributes: bool,
    indent: str = "  ",
) -> list[str]:
    attrs: list[str] = [_attribute("history_id", run["history_id"])]
    if (status := run["result"]["status"]) is not None:
        attrs.append(_attribute("status", status))
    if cwd := run["context"]["cwd"]:
        attrs.append(_attribute("cwd", cwd))
    if (duration := run["timing"]["duration"]) is not None:
        attrs.append(_attribute("duration_ms", _duration_ms(duration)))
    if recorded_at := run["timing"].get("recorded_at"):
        attrs.append(_attribute("recorded_at", recorded_at))

    lines = _opening_tag(
        "run",
        attrs,
        indent=indent,
        pretty_attributes=pretty_attributes,
    ).splitlines()
    if git := run["context"].get("git"):
        lines.extend(_render_git(git, indent=f"{indent}  ", pretty_attributes=pretty_attributes))
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
    if value := environment.get("os"):
        details.append(f"os {_inline_value(value)}")
    if value := environment.get("arch"):
        details.append(f"arch {_inline_value(value)}")
    if value := environment.get("login_shell"):
        details.append(f"login_shell {_inline_value(value)}")
    if value := environment.get("hostname"):
        details.append(f"hostname {_inline_value(value)}")
    if value := environment.get("session_id"):
        details.append(f"session_id {_inline_value(value)}")
    if (python_context := environment.get("python")) and (version := python_context.get("version")):
        details.append(f"python {_inline_value(version)}")
    return details


def _render_markdown(record: CopoutRecord) -> str:
    lines: list[str] = []
    if environment := record.get("environment"):
        details = _markdown_environment(environment)
        if details:
            details.append(f"captured_at {_inline_value(record['captured_at'])}")
            lines.extend(("### Environment", "", " · ".join(details), ""))

    runs = _record_runs(record)
    for index, run in enumerate(runs, start=1):
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"### Run {index}" if len(runs) > 1 else "### Command")
        details: list[str] = []
        if (status := run["result"]["status"]) is not None:
            details.append(f"exit {status}")
        if cwd := run["context"]["cwd"]:
            details.append(f"cwd {_inline_value(cwd)}")
        if (duration := run["timing"]["duration"]) is not None:
            details.append(f"{_duration_ms(duration)} ms")
        if recorded_at := run["timing"].get("recorded_at"):
            details.append(f"recorded_at {_inline_value(recorded_at)}")
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

    attrs = [
        _attribute("version", projected["version"]),
        _attribute("captured_at", projected["captured_at"]),
    ]
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
                pretty_attributes=pretty_attributes,
            )
        )
    lines.append("</copout>")
    return "\n".join(lines) + "\n"
