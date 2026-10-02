"""Integration tests for the FastAPI-mounted MCP server (fastapi-mcp)."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest
import uvicorn
from fastapi_mcp import FastApiMCP
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.shared.memory import create_connected_server_and_client_session

from criticat.interfaces.api import ReviewDependencies
from criticat.interfaces.mcp import (
    MCP_MOUNT_PATH,
    combined_app,
    create_mcp,
    parse_args,
    run_server,
)
from criticat.models.config import environment
from tests.factories import FakeReviewPDFFactory


def text_of(result: types.CallToolResult) -> str:
    content = result.content[0]
    assert isinstance(content, types.TextContent)
    return content.text


@pytest.fixture
def bridge(override_dependencies: ReviewDependencies) -> FastApiMCP:
    return create_mcp(combined_app)


def connected(bridge: FastApiMCP) -> AbstractAsyncContextManager[ClientSession]:
    return create_connected_server_and_client_session(bridge.server)


@pytest.mark.anyio
async def test_exposes_only_public_operations(bridge: FastApiMCP) -> None:
    async with connected(bridge) as session:
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        assert set(tools) == {"review_pdf", "health_check"}
        schema = tools["review_pdf"].inputSchema
        assert "pdf_path" in schema["properties"]
        assert "pdf_path" in schema.get("required", [])


@pytest.mark.anyio
async def test_health_tool_calls_api_in_process(bridge: FastApiMCP) -> None:
    async with connected(bridge) as session:
        result = await session.call_tool("health_check", {})
        assert not result.isError
        assert json.loads(text_of(result)) == {
            "status": "healthy",
            "service": "Criticat API",
        }


@pytest.mark.anyio
async def test_review_tool_runs_review(
    bridge: FastApiMCP, fake_pdf: Path, review_factory: FakeReviewPDFFactory
) -> None:
    async with connected(bridge) as session:
        result = await session.call_tool(
            "review_pdf", {"pdf_path": str(fake_pdf), "joke_mode": "none"}
        )
        assert not result.isError, text_of(result)
        body = json.loads(text_of(result))
        assert set(body) == {"review_feedback", "jokes"}
        assert len(review_factory.run_configs) == 1


@pytest.mark.anyio
async def test_review_tool_surfaces_validation_errors(
    bridge: FastApiMCP, tmp_path: Path
) -> None:
    async with connected(bridge) as session:
        result = await session.call_tool(
            "review_pdf", {"pdf_path": str(tmp_path / "missing.pdf")}
        )
        assert result.isError
        assert "PDF file not found" in text_of(result)


def test_mcp_routes_are_mounted() -> None:
    paths = {getattr(route, "path", None) for route in combined_app.routes}
    assert MCP_MOUNT_PATH in paths
    assert f"{MCP_MOUNT_PATH}/messages/" in paths


def test_parse_args_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment.settings, "server_host", "127.0.0.9")
    monkeypatch.setattr(environment.settings, "server_port", 8123)
    args = parse_args([])
    assert (args.host, args.port, args.reload) == ("127.0.0.9", 8123, False)


def test_run_server_passes_options(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        uvicorn, "run", lambda app, **kwargs: calls.append({"app": app, **kwargs})
    )
    run_server(["--host", "127.0.0.1", "--port", "9000", "--reload"])
    assert calls == [
        {
            "app": "criticat.interfaces.mcp:combined_app",
            "host": "127.0.0.1",
            "port": 9000,
            "reload": True,
        }
    ]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def live_server(override_dependencies: ReviewDependencies) -> Iterator[str]:
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(combined_app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.mark.anyio
async def test_sse_transport_end_to_end(live_server: str, fake_pdf: Path) -> None:
    async with (
        sse_client(f"{live_server}{MCP_MOUNT_PATH}") as (read, write),
        ClientSession(read, write) as session,
    ):
        init = await session.initialize()
        assert init.serverInfo.name == "Criticat"

        tools = {tool.name for tool in (await session.list_tools()).tools}
        assert tools == {"review_pdf", "health_check"}

        health = await session.call_tool("health_check", {})
        assert json.loads(text_of(health))["status"] == "healthy"

        review = await session.call_tool("review_pdf", {"pdf_path": str(fake_pdf)})
        assert not review.isError, text_of(review)
        assert "review_feedback" in json.loads(text_of(review))
