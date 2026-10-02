"""
FastAPI interface for Criticat PDF review service.

Provides RESTful API endpoints for interacting with the PDF review functionality.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from criticat.infrastructure.di.providers import (
    ReviewDependencies,
    get_review_dependencies,
)
from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.formatting import FormatReview
from criticat.models.states.review import ReviewState
from criticat.use_cases.service import ReviewInputError, validate_pdf_path

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ReviewRequest(BaseModel):
    """
    Request model for PDF review.

    Attributes
    ----------
    pdf_path : str
        Path to the PDF file to review.
    project_id : Optional[str]
        Google Cloud project ID (defaults to environment variable).
    location : Optional[str]
        Google Cloud location (defaults to environment variable or 'us-central1').
    joke_mode : JokeMode
        Mode for injecting cat jokes (none, default, chaotic).
    """

    pdf_path: str = Field(description="Path to the PDF file to review")
    project_id: str | None = Field(
        default=None,
        description="Google Cloud project ID (defaults to CRITICAT_GCP_PROJECT_ID environment variable)",
    )
    location: str | None = Field(
        default=None,
        description="Google Cloud location (defaults to CRITICAT_GCP_LOCATION environment variable or 'us-central1')",
    )
    joke_mode: JokeMode = Field(
        default=JokeMode.DEFAULT,
        description="Mode for injecting cat jokes (none, default, chaotic)",
    )


class ReviewResponse(BaseModel):
    """
    Response model for PDF review results.

    Attributes
    ----------
    review_feedback : Dict[str, FormatReview]
        LLM feedback on the document, keyed by provider name.
    jokes : List[str]
        List of cat jokes injected in the review.
    """

    review_feedback: dict[str, FormatReview] = Field(
        default_factory=dict, description="LLM feedback on the document"
    )
    jokes: list[str] = Field(
        default_factory=list, description="List of cat jokes injected in the review"
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan events.

    Configures the dependency container on startup.
    """
    logger.info("Dependency container configured")
    yield
    # Add shutdown logic here if needed in the future
    logger.info("Application shutdown.")


app = FastAPI(
    title="Criticat API",
    description="API for reviewing PDF documents and generating formatting feedback",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post(
    "/review",
    operation_id="review_pdf",
    response_model=ReviewResponse,
    description="Review a PDF document and generate formatting feedback",
)
async def review_pdf(
    request: ReviewRequest,
    deps: ReviewDependencies = Depends(get_review_dependencies),
) -> ReviewResponse:
    """
    Review a PDF document and generate a report with formatting feedback.

    Parameters
    ----------
    request : ReviewRequest
        The review request parameters.
    deps : ReviewDependencies
        Dependency container with required services.

    Returns
    -------
    ReviewResponse
        ReviewResponse containing the review results

    Raises
    ------
    HTTPException
        If the input is invalid (400) or an internal error occurs (500).
    """
    try:
        logger.info(f"Received review request for PDF: {request.pdf_path}")

        try:
            pdf_path = validate_pdf_path(request.pdf_path)
        except ReviewInputError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        project_id = request.project_id or deps.get_project_id()
        if not project_id:
            raise HTTPException(
                status_code=400,
                detail="No GCP project ID provided. Either set CRITICAT_GCP_PROJECT_ID environment variable or provide project_id in the request.",
            )

        location = request.location or deps.get_location()

        config = ReviewConfig(
            pdf_path=str(pdf_path),
            joke_mode=request.joke_mode,
        )

        provider_config = deps.provider_config_factory(
            project_id=project_id,
            location=location,
        )

        review_use_case = deps.review_pdf_factory(provider_configs=[provider_config])

        logger.info("Starting review process...")
        final_state = await run_in_threadpool(
            review_use_case._run, config=config.model_dump()
        )
        review = ReviewState.model_validate(final_state["review"], from_attributes=True)

        logger.info("Review completed successfully")

        return ReviewResponse(
            review_feedback=review.review_feedback,
            jokes=review.jokes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during PDF review")
        raise HTTPException(status_code=500, detail=f"Review failed: {e!s}") from e


@app.get("/health", operation_id="health_check", description="Health check endpoint")
async def health_check() -> dict[str, str]:
    """
    Provide a simple health check endpoint.

    Returns
    -------
    Dict[str, str]
        Status message
    """
    return {"status": "healthy", "service": "Criticat API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("criticat.interfaces.api:app", host="0.0.0.0", port=8000, reload=True)
