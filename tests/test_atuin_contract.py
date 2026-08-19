from __future__ import annotations

import shutil

import pytest

from copout.atuin_mcp import MCPClient, find_tool


@pytest.mark.component
@pytest.mark.slow
@pytest.mark.skipif(
    shutil.which("atuin") is None,
    reason="Atuin is not installed",
)
def test_live_atuin_mcp_exposes_history_tool() -> None:
    with MCPClient(timeout=5.0) as client:
        tools = client.tools()

    history = find_tool(tools, "history")

    assert history is not None
    assert history.name
    assert isinstance(history.schema, dict)
