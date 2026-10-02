"""
Dependency injection container module for Criticat.
Uses dependency-injector to manage application dependencies.
"""

import logging

from dependency_injector import containers, providers

from criticat.models.config.environment import get_gcp_location, get_gcp_project_id
from criticat.models.models import VertexAIConfig
from criticat.use_cases.review import ReviewPDF

logger = logging.getLogger(__name__)


class Container(containers.DeclarativeContainer):
    """
    Dependency Injection container for Criticat application.
    Manages and provides all application dependencies.
    """

    # Configuration providers
    config = providers.Configuration()

    # Direct providers for environment variables
    get_project_id = providers.Callable(get_gcp_project_id)
    get_location = providers.Callable(get_gcp_location)

    # Factory providers
    provider_config_factory = providers.Factory(
        VertexAIConfig,
        project_id=get_project_id,
        location=get_location,
    )

    review_pdf_factory = providers.Factory(
        ReviewPDF,
        provider_configs=providers.List(
            providers.Callable(
                lambda config_factory=provider_config_factory: [config_factory()],
            ),
        ),
    )


# Application container instance
container = Container()
