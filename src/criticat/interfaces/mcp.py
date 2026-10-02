"""
FastAPI-MCP integration for Criticat PDF review service.

Mounts an MCP server (SSE at ``/mcp``) onto the FastAPI app so the REST
endpoints are also available as MCP tools.
"""

import argparse
import logging
from collections.abc import Sequence

import httpx
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from criticat.interfaces.api import app as fastapi_app
from criticat.models.config.environment import settings

logger = logging.getLogger(__name__)

MCP_MOUNT_PATH = "/mcp"
MCP_OPERATIONS = ["review_pdf", "health_check"]
INTERNAL_BASE_URL = "http://criticat.internal"


def create_mcp(app: FastAPI = fastapi_app) -> FastApiMCP:
    """
    Build the FastApiMCP bridge for ``app``.

    Tool calls are dispatched in-process through an ASGI transport, so they work
    regardless of the host/port the server is bound to.
    """
    return FastApiMCP(
        app,
        name="Criticat",
        description="Criticat - A Tool for Analyzing Latex PDFs",
        base_url=INTERNAL_BASE_URL,
        http_client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=INTERNAL_BASE_URL,
            timeout=None,
        ),
        include_operations=MCP_OPERATIONS,
        describe_all_responses=True,
        describe_full_response_schema=True,
    )


def mount_mcp_to_fastapi(app: FastAPI = fastapi_app) -> FastAPI:
    """
    Mount the MCP server to the FastAPI application.

    Returns:
        FastAPI application with MCP mounted
    """
    logger.info("Mounting MCP server to FastAPI application")
    create_mcp(app).mount(app, mount_path=MCP_MOUNT_PATH)
    logger.info("MCP server mounted at %s", MCP_MOUNT_PATH)
    return app


combined_app = mount_mcp_to_fastapi()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="criticat-api",
        description="Run the Criticat REST API with MCP (SSE) mounted at /mcp.",
    )
    parser.add_argument(
        "--host",
        default=settings.server_host,
        help="Bind host (env: CRITICAT_SERVER_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.server_port,
        help="Bind port (env: CRITICAT_SERVER_PORT)",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    return parser.parse_args(argv)


def run_server(argv: Sequence[str] | None = None) -> None:
    """
    Entry point function to run the combined FastAPI and MCP server.
    This function is used by the pyproject.toml script entry.
    """
    import uvicorn

    args = parse_args(argv)
    uvicorn.run(
        "criticat.interfaces.mcp:combined_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    run_server()
