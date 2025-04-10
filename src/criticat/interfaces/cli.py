"""
Command-line interface for Criticat using Typer.
"""

import logging
import sys

import typer

from criticat.flow import run_review_graph
from criticat.models.models import CriticatConfig, JokeMode


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

app = typer.Typer(help="Criticat - A GitHub Action for analyzing PDFs")


@app.command()
def review(
    pdf_path: str = typer.Option(
        ..., "--pdf-path", help="Path to the PDF file to review"
    ),
    project_id: str = typer.Option(..., "--project-id", help="Google Cloud project ID"),
    location: str = typer.Option(
        "us-central1", "--location", help="Google Cloud location"
    ),
    repository: str | None = typer.Option(
        metavar="--repository",
        default=None,
        help="GitHub repository in format owner/repo",
    ),
    github_token: str | None = typer.Option(
        metavar="--github-token", default=None, help="GitHub token for API access"
    ),
    pr_number: int | None = typer.Option(
        metavar="--pr-number", default=None, help="Pull request number to comment on"
    ),
    joke_mode: JokeMode = typer.Option(
        JokeMode.DEFAULT,
        "--joke-mode",
        help="Mode for injecting cat jokes: none, default, or chaotic",
    ),
) -> None:
    """
    Review a PDF document and comment on GitHub PR if issues are found.
    """
    logger.info(f"Starting Criticat review for {pdf_path}")

    try:
        # Create config
        config = CriticatConfig(
            pdf_path=pdf_path,
            project_id=project_id,
            location=location,
            github_token=github_token,
            repository=repository,
            pr_number=pr_number,
            joke_mode=joke_mode,
        )

        # Run review flow directly
        run_review_graph(config.model_dump())

        logger.info("Review completed successfully")
    except Exception as e:
        logger.error(f"Error during review: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
