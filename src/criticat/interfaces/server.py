"""
Context Model Protocol (CMP) server implementation for Criticat.
Uses the MCP framework to provide tools and resources.
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

from criticat.models import CriticatConfig, JokeMode
from criticat.flow import run_review_graph


logger = logging.getLogger(__name__)

# Create the MCP server
mcp = FastMCP(name="Criticat")


# Register the review tool
@mcp.tool()
def review(
    pdf_path: str,
    project_id: str,
    location: str = "us-central1",
    github_token: str = "",
    repository: str = "",
    pr_number: int = 0,
    joke_mode: str = "default",
) -> Dict[str, Any]:
    """
    Review a PDF document and comment on GitHub PR if issues are found.

    Args:
        pdf_path: Path to the PDF file to review
        project_id: Google Cloud project ID
        location: Google Cloud location
        github_token: GitHub token for API access
        repository: GitHub repository in format owner/repo
        pr_number: Pull request number to comment on
        joke_mode: Mode for injecting cat jokes (none, default, chaotic)

    Returns:
        Review results
    """
    logger.info(f"MCP review tool called for PDF: {pdf_path}")

    # Convert joke_mode string to enum
    joke_mode_enum = JokeMode(joke_mode)

    # Create configuration
    config = CriticatConfig(
        pdf_path=pdf_path,
        project_id=project_id,
        location=location,
        github_token=github_token,
        repository=repository,
        pr_number=pr_number,
        joke_mode=joke_mode_enum,
    )

    # Run review
    result = run_review_graph(config.model_dump())

    # Return results
    return result
