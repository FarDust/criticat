"""
FastAPI-specific dependency providers for Criticat.
Bridges the gap between the dependency-injector container and FastAPI's dependency injection system.
"""

import logging
from typing import Callable, Optional

from fastapi import Depends
from pydantic import BaseModel

from criticat.infrastructure.di.container import container
from criticat.use_cases.review import ReviewPDF

logger = logging.getLogger(__name__)
# Remove inject/Provide imports if no longer needed here
# from dependency_injector.wiring import inject, Provide


class ReviewDependencies:
    """Container for all dependencies required by the review endpoint."""

    def __init__(
        self,
        review_pdf_factory: Callable[[list[BaseModel]], ReviewPDF],
        provider_config_factory: Callable[[str, str], BaseModel],
        get_project_id: Callable[[], Optional[str]],
        get_location: Callable[[], str],
    ):
        self.review_pdf_factory = review_pdf_factory
        self.provider_config_factory = provider_config_factory
        self.get_project_id = get_project_id
        self.get_location = get_location


# Remove @inject decorator
def get_review_dependencies(
    # Inject the container itself
    app_container: container.__class__ = Depends(lambda: container),
) -> ReviewDependencies:
    """
    Dependency provider for review-related dependencies.
    Resolves dependencies from the container inside the function body.
    """
    # Get the providers themselves
    get_project_id_provider = app_container.get_project_id
    get_location_provider = app_container.get_location
    provider_config_factory_provider = app_container.provider_config_factory
    review_pdf_factory_provider = app_container.review_pdf_factory

    return ReviewDependencies(
        # Pass the providers/factories themselves
        review_pdf_factory=review_pdf_factory_provider,
        provider_config_factory=provider_config_factory_provider,
        get_project_id=get_project_id_provider,
        get_location=get_location_provider,
    )


def get_container():
    """
    Return the application container.
    Useful for setup and configuration.
    """
    return container
