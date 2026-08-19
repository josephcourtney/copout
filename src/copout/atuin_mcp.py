from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from typing import Any


class AtuinError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict[str, Any]


class MCPClient(AbstractContextManager["MCPClient"]):
    """Minimal stdio MCP client for Atuin's public `atuin mcp` interface."""

    def __init__(self, command: list[str] | None = None, *, timeout: float = 3.0) -> None:
        self.command = command or ["atuin", "mcp"]
        self.timeout = timeout
        self._proc: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._next_id = 1
        self._reader: threading.Thread | None = None

    def __enter__(self) -> MCPClient:
        if shutil.which(self.command[0]) is None:
            msg = "Atuin is required but `atuin` is not on PATH"
            raise AtuinError(msg)

        try:
            self._proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=os.environ.copy(),
            )
        except OSError as exc:
            msg = f"failed to start Atuin MCP server: {exc}"
            raise AtuinError(msg) from exc

        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

        try:
            self._initialize()
        except BaseException:
            self.close()
            raise

        return self

    def close(self) -> None:
        proc = self._proc
        self._proc = None

        if proc is None:
            return

        if proc.stdin is not None:
            with suppress(OSError):
                proc.stdin.close()

        try:
            proc.terminate()
            proc.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            with suppress(OSError):
                proc.kill()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _read_stdout(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return

        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self._responses.put(message)

    def _send(self, payload: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise AtuinError("Atuin MCP server is not running")
        try:
            proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except OSError as exc:
            raise AtuinError(f"failed to communicate with Atuin MCP server: {exc}") from exc

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        deadline = time.monotonic() + self.timeout
        deferred: list[dict[str, Any]] = []
        try:
            while time.monotonic() < deadline:
                try:
                    message = self._responses.get(timeout=max(0.01, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if message.get("id") == request_id:
                    if "error" in message:
                        error = message.get("error")
                        raise AtuinError(f"Atuin MCP error for {method}: {error}")
                    result = message.get("result")
                    if not isinstance(result, dict):
                        return {"value": result}
                    return result
                deferred.append(message)
        finally:
            for message in deferred:
                self._responses.put(message)
        raise AtuinError(f"timed out waiting for Atuin MCP method {method}")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _initialize(self) -> None:
        versions = ("2025-06-18", "2025-03-26", "2024-11-05")
        last_error: AtuinError | None = None
        for version in versions:
            try:
                self._request(
                    "initialize",
                    {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "copout", "version": "0.7.4"},
                    },
                )
                self._notify("notifications/initialized")
                return
            except AtuinError as exc:
                last_error = exc
        raise last_error or AtuinError("could not initialize Atuin MCP server")

    def tools(self) -> dict[str, Tool]:
        result = self._request("tools/list")
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list):
            return {}
        tools: dict[str, Tool] = {}
        for raw in raw_tools:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "")
            schema = raw.get("inputSchema")
            if name:
                tools[name.lower()] = Tool(
                    name=name, schema=schema if isinstance(schema, dict) else {}
                )
        return tools

    def call(self, tool: Tool, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("tools/call", {"name": tool.name, "arguments": arguments})


def find_tool(tools: dict[str, Tool], suffix: str) -> Tool | None:
    suffix = suffix.lower()
    exact = tools.get(f"atuin_{suffix}")
    if exact is not None:
        return exact
    for key, tool in tools.items():
        normalized = key.replace("-", "_")
        if normalized.endswith(suffix) or normalized.endswith(f"_{suffix}"):
            return tool
    return None


def tool_arguments(
    tool: Tool,
    *,
    session: bool = True,
    limit: int | None = None,
    failed_only: bool = False,
    history_id: str | None = None,
) -> dict[str, Any]:
    properties = tool.schema.get("properties")
    props = properties if isinstance(properties, dict) else {}
    args: dict[str, Any] = {}

    def set_first(names: tuple[str, ...], value: Any) -> None:
        for name in names:
            if name in props:
                args[name] = value
                return

    if history_id is not None:
        set_first(("history_id", "historyId", "id"), history_id)
        return args

    required_raw = tool.schema.get("required")
    required = set(required_raw) if isinstance(required_raw, list) else set()
    for name in ("query", "search", "term"):
        if name in props and name in required:
            args[name] = ""
            break
    if session:
        # Atuin 18.17 exposed a singular filter-mode shape in early MCP builds,
        # while 18.19 requires `filter_modes`. Discover the live schema and send
        # the representation it declares rather than coupling Copout to one release.
        if "filter_modes" in props:
            schema = props.get("filter_modes")
            if isinstance(schema, dict) and schema.get("type") == "string":
                args["filter_modes"] = "session"
            else:
                args["filter_modes"] = ["session"]
        else:
            set_first(("filter_mode", "filterMode", "filter", "scope"), "session")
    if limit is not None:
        set_first(("limit", "max_results", "maxResults", "count"), limit)
    if failed_only:
        set_first(("failed_only", "failedOnly", "failed"), True)
    return args
