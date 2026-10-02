"""End-to-end test of ``criticat-mcp`` over a real stdio subprocess."""

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from tests.conftest import requires_poppler

pytestmark = pytest.mark.anyio


def text_of(result: types.CallToolResult) -> str:
    content = result.content[0]
    assert isinstance(content, types.TextContent)
    return content.text


@requires_poppler
async def test_stdio_server_round_trip(tmp_path: Path, sample_pdf: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "criticat.interfaces.server"],
        env={**os.environ, "CRITICAT_LOG_LEVEL": "DEBUG"},
        cwd=tmp_path,
    )
    stderr_log = tmp_path / "server.stderr"

    with stderr_log.open("w") as errlog:
        async with (
            stdio_client(params, errlog=errlog) as (read, write),
            ClientSession(read, write) as session,
        ):
            init = await session.initialize()
            assert init.serverInfo.name == "Criticat"

            tools = {tool.name for tool in (await session.list_tools()).tools}
            assert {"review_pdf", "validate_pdf", "check_configuration"} <= tools

            validated = await session.call_tool(
                "validate_pdf", {"pdf_path": str(sample_pdf)}
            )
            assert not validated.isError
            assert json.loads(text_of(validated))["page_count"] == 2

            config = json.loads(
                text_of(await session.call_tool("check_configuration", {}))
            )
            assert config["ready"] is False
            assert config["project_id"] is None

            review = await session.call_tool(
                "review_pdf", {"pdf_path": str(sample_pdf)}
            )
            assert review.isError
            assert "No GCP project ID provided" in text_of(review)

            categories = await session.read_resource("criticat://format-categories")  # type: ignore[arg-type]
            assert categories.contents

    assert "Starting Criticat MCP server" in stderr_log.read_text()
