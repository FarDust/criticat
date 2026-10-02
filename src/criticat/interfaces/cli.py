"""
Command-line interface for Criticat using Typer.
"""

import logging
import sys

import typer

from criticat.models.config.app import JokeMode
from criticat.reporting import render_review_markdown
from criticat.use_cases.service import ReviewError, ReviewService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

app = typer.Typer(help="Criticat - A GitHub Action for analyzing PDFs")


@app.command(
    help="Analyzes a PDF document for formatting issues using Vertex AI and optionally comments on a GitHub PR."
)
def review(
    pdf_path: str = typer.Option(
        ..., "--pdf-path", help="Path to the PDF file to review"
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Google Cloud project ID",
        envvar=["CRITICAT_GCP_PROJECT_ID"],
    ),
    location: str = typer.Option(
        "us-central1",
        "--location",
        help="Google Cloud location",
        envvar=["CRITICAT_GCP_LOCATION"],
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
    Review a PDF document using specified configurations.

    Optionally comments on a GitHub Pull Request if repository, PR number,
    and token are provided and significant issues are found during the review.
    Exits with status code 1 if errors occur or required parameters are missing.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file to review.
    project_id : str | None
        Google Cloud project ID. Reads from CRITICAT_GCP_PROJECT_ID env var if None.
    location : str
        Google Cloud location. Reads from CRITICAT_GCP_LOCATION env var if not specified.
    repository : str | None, optional
        GitHub repository in 'owner/repo' format. Required for PR commenting.
    github_token : str | None, optional
        GitHub token for API access. Required for PR commenting.
    pr_number : int | None, optional
        Pull request number to comment on. Required for PR commenting.
    joke_mode : JokeMode
        Mode for injecting cat jokes ('none', 'default', 'chaotic').
    """
    logger.info(f"Starting Criticat review for {pdf_path}")

    try:
        review_state = ReviewService().run(
            pdf_path=pdf_path,
            project_id=project_id,
            location=location,
            joke_mode=joke_mode,
        )
    except ReviewError as e:
        logger.error("Review failed: %s", e)
        sys.exit(1)

    typer.echo(render_review_markdown(review_state))
    logger.info("Review completed successfully")


if __name__ == "__main__":
    app()
