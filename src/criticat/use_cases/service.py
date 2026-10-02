"""
Interface-agnostic review service.

Validates user input, resolves cloud configuration and runs the ``ReviewPDF``
graph. Shared by the CLI, the REST API and the MCP server so every entry point
behaves the same way.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.config.environment import get_gcp_location, get_gcp_project_id
from criticat.models.models import VertexAIConfig
from criticat.models.states.review import ReviewState
from criticat.use_cases.review import ReviewPDF

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"


class ReviewError(Exception):
    """Base class for review failures."""


class ReviewInputError(ReviewError, ValueError):
    """Raised when the caller supplied invalid input."""


class ReviewExecutionError(ReviewError, RuntimeError):
    """Raised when the review pipeline fails."""


class ReviewRunner(Protocol):
    def _run(self, config: dict[str, Any]) -> dict[str, Any]: ...


ReviewPDFFactory = Callable[..., ReviewRunner]


@dataclass(frozen=True)
class PreparedReview:
    config: ReviewConfig
    provider_config: VertexAIConfig


def validate_pdf_path(pdf_path: str) -> Path:
    """Return the resolved path of a readable PDF or raise ``ReviewInputError``."""
    if not pdf_path or not pdf_path.strip():
        raise ReviewInputError("pdf_path must not be empty.")

    path = Path(pdf_path.strip()).expanduser().resolve()
    if not path.exists():
        raise ReviewInputError(f"PDF file not found: {path}")
    if not path.is_file():
        raise ReviewInputError(f"PDF path is not a file: {path}")
    if path.suffix.lower() != ".pdf":
        raise ReviewInputError(f"Expected a .pdf file, got: {path.name}")

    try:
        with path.open("rb") as handle:
            header = handle.read(len(PDF_MAGIC))
    except OSError as e:
        raise ReviewInputError(f"PDF file is not readable: {path} ({e})") from e

    if header != PDF_MAGIC:
        raise ReviewInputError(f"File does not look like a PDF document: {path}")

    return path


def resolve_joke_mode(joke_mode: str | JokeMode) -> JokeMode:
    if isinstance(joke_mode, JokeMode):
        return joke_mode
    try:
        return JokeMode(joke_mode.strip().lower())
    except (ValueError, AttributeError) as e:
        valid = ", ".join(mode.value for mode in JokeMode)
        raise ReviewInputError(
            f"Invalid joke_mode: {joke_mode!r}. Expected one of: {valid}."
        ) from e


class ReviewService:
    """Run PDF reviews with validated input and resolved provider configuration."""

    def __init__(
        self,
        review_pdf_factory: ReviewPDFFactory = ReviewPDF,
        project_id_resolver: Callable[[], str | None] = get_gcp_project_id,
        location_resolver: Callable[[], str] = get_gcp_location,
    ) -> None:
        self._review_pdf_factory = review_pdf_factory
        self._project_id_resolver = project_id_resolver
        self._location_resolver = location_resolver

    def resolve_project_id(self, project_id: str | None = None) -> str:
        resolved = (project_id or "").strip() or self._project_id_resolver()
        if not resolved:
            raise ReviewInputError(
                "No GCP project ID provided. Either set CRITICAT_GCP_PROJECT_ID "
                "environment variable or provide project_id."
            )
        return resolved

    def resolve_location(self, location: str | None = None) -> str:
        return (location or "").strip() or self._location_resolver()

    def prepare(
        self,
        pdf_path: str,
        project_id: str | None = None,
        location: str | None = None,
        joke_mode: str | JokeMode = JokeMode.DEFAULT,
    ) -> PreparedReview:
        path = validate_pdf_path(pdf_path)
        mode = resolve_joke_mode(joke_mode)
        provider_config = VertexAIConfig(
            project_id=self.resolve_project_id(project_id),
            location=self.resolve_location(location),
        )
        return PreparedReview(
            config=ReviewConfig(pdf_path=str(path), joke_mode=mode),
            provider_config=provider_config,
        )

    def execute(self, prepared: PreparedReview) -> ReviewState:
        provider_configs: list[BaseModel] = [prepared.provider_config]
        try:
            use_case = self._review_pdf_factory(provider_configs=provider_configs)
            final_state = use_case._run(config=prepared.config.model_dump())
        except ReviewError:
            raise
        except Exception as e:
            logger.exception("Review pipeline failed")
            raise ReviewExecutionError(f"Review failed: {e}") from e

        review = final_state.get("review") if isinstance(final_state, dict) else None
        if review is None:
            raise ReviewExecutionError("Review pipeline returned no 'review' state.")
        try:
            return ReviewState.model_validate(review, from_attributes=True)
        except ValueError as e:
            raise ReviewExecutionError(
                f"Review pipeline returned an invalid review state: {e}"
            ) from e

    def run(
        self,
        pdf_path: str,
        project_id: str | None = None,
        location: str | None = None,
        joke_mode: str | JokeMode = JokeMode.DEFAULT,
    ) -> ReviewState:
        return self.execute(
            self.prepare(
                pdf_path=pdf_path,
                project_id=project_id,
                location=location,
                joke_mode=joke_mode,
            )
        )
