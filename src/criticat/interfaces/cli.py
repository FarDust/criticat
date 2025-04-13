"""
Command-line interface for Criticat using Typer.
"""

import logging
import sys

import typer

from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.models import VertexAIConfig
from criticat.use_cases.review import ReviewPDF


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
        config = ReviewConfig(
            pdf_path=pdf_path,
            joke_mode=joke_mode,
        )

        review_use_case = ReviewPDF(
            provider_configs=[
                VertexAIConfig(
                    project_id=project_id,
                    location=location,
                ),
            ]
        )

        review_use_case._run(
            config=config.model_dump(),
        )

        logger.info("Review completed successfully")
    except Exception as e:
        logger.error(f"Error during review: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
