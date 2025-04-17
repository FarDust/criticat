"""
FastAPI interface for Criticat PDF review service.

Provides RESTful API endpoints for interacting with the PDF review functionality.
"""

import logging
from typing import Dict, List, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.formatting import FormatReview
from criticat.infrastructure.di.providers import (
    get_review_dependencies,
    ReviewDependencies,
)


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
    location : str
        Google Cloud location (defaults to environment variable or 'us-central1').
    joke_mode : JokeMode
        Mode for injecting cat jokes (none, default, chaotic).
    """

    pdf_path: str = Field(description="Path to the PDF file to review")
    project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID (defaults to CRITICAT_GCP_PROJECT_ID environment variable)",
    )
    location: str = Field(
        default="us-central1",
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

    review_feedback: Dict[str, FormatReview] = Field(
        default_factory=dict, description="LLM feedback on the document"
    )
    jokes: List[str] = Field(
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
    response_model=ReviewResponse,
    description="Review a PDF document and generate formatting feedback",
)
async def review_pdf(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    deps: ReviewDependencies = Depends(get_review_dependencies),
) -> ReviewResponse:
    """
    Review a PDF document and generate a report with formatting feedback.

    Parameters
    ----------
    request : ReviewRequest
        The review request parameters.
    background_tasks : BackgroundTasks
        FastAPI background tasks manager.
    deps : ReviewDependencies
        Dependency container with required services.

    Returns
    -------
    ReviewResponse
        ReviewResponse containing the review results

    Raises
    ------
    HTTPException
        If project_id is missing (400) or an internal error occurs (500).
    """
    try:
        logger.info(f"Received review request for PDF: {request.pdf_path}")

        project_id = (
            request.project_id or deps.get_project_id()
        )
        if not project_id:
            raise HTTPException(
                status_code=400,
                detail="No GCP project ID provided. Either set CRITICAT_GCP_PROJECT_ID environment variable or provide project_id in the request.",
            )

        location = request.location or deps.get_location()

        config = ReviewConfig(
            pdf_path=request.pdf_path,
            joke_mode=request.joke_mode,
        )

        provider_config = deps.provider_config_factory(
            project_id=project_id,
            location=location,
        )

        review_use_case = deps.review_pdf_factory(
            provider_configs=[provider_config]
        )

        logger.info("Starting review process...")
        final_state = review_use_case._run(
            config=config.model_dump(),
        )

        logger.info("Review completed successfully")

        return ReviewResponse(
            review_feedback=final_state[
                "review"
            ].review_feedback,
            jokes=final_state["review"].jokes,
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error during PDF review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")


@app.get("/health", description="Health check endpoint")
async def health_check() -> Dict[str, str]:
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
