"""
FastAPI-MCP integration for Criticat PDF review service.
This module mounts the MCP server to FastAPI, enabling both REST and MCP protocols.
"""

import logging
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from criticat.interfaces.api import app as fastapi_app

logger = logging.getLogger(__name__)


def mount_mcp_to_fastapi() -> FastAPI:
    """
    Mount the MCP server to the FastAPI application.

    Returns:
        FastAPI application with MCP mounted
    """
    logger.info("Mounting MCP server to FastAPI application")

    # Create the FastApiMCP instance to mount the MCP server to FastAPI
    # Use the actual MCP instance from server.py
    fastapi_mcp = FastApiMCP(
        fastapi_app,
        name="Criticat",
        description="Criticat - A Tool for Analyzing Latex PDFs",
        describe_all_responses=True,
        describe_full_response_schema=True,
    )

    # Mount the MCP server
    fastapi_mcp.mount()

    logger.info("MCP server mounted to FastAPI application")
    return fastapi_app


# Initialize the combined app when imported
combined_app = mount_mcp_to_fastapi()


def run_server() -> None:
    """
    Entry point function to run the combined FastAPI and MCP server.
    This function is used by the pyproject.toml script entry.
    """
    import uvicorn

    uvicorn.run(
        "criticat.interfaces.mcp:combined_app",
    )


if __name__ == "__main__":
    run_server()
