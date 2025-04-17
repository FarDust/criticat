"""
Pytest configuration for Criticat tests.

Contains shared fixtures and mock implementations for testing.
"""

from typing import Dict, Any, Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from criticat.interfaces.api import ReviewDependencies, app, get_review_dependencies
from criticat.models.formatting import (
    FormatReview,
    FormatCategoryItem,
    FormatIssue,
)
from criticat.models.config.app import ReviewConfig
from criticat.models.states.control import ControlState, ControllableConfig
from criticat.models.states.review import ReviewState


class MockVertexAIConfig(BaseModel):
    """Mock configuration for Vertex AI LLM provider."""

    llm_provider: str = "vertex_ai"
    project_id: str
    location: str = "us-central1"


class MockReviewPDF:
    """Mock implementation of ReviewPDF for testing."""

    def __init__(self, provider_configs: list[BaseModel]) -> None:
        """
        Initialize the mock ReviewPDF use case.

        Parameters
        ----------
        provider_configs : list[BaseModel]
            A list of provider configuration objects.
        """
        self.provider_configs = provider_configs
        # Store configurations for assertions in tests
        self.project_id = provider_configs[0].project_id if provider_configs else None
        self.location = provider_configs[0].location if provider_configs else None

    def _run(self, config: Dict[str, Any]) -> Dict[str, Any]:  # Change return type hint
        """
        Mock implementation of the _run method.

        Returns a dictionary containing a mock ReviewState object under the key "review",
        mimicking the structure expected by the API endpoint for testing purposes.

        Parameters
        ----------
        config : Dict[str, Any]
            The configuration dictionary passed to the use case.

        Returns
        -------
        Dict[str, Any]
            A dictionary containing the mock ReviewState under the key "review".
        """
        # Create a sample format issue
        format_issue = FormatIssue(
            description="Inconsistent spacing between paragraphs",
            explanation="The spacing between paragraphs varies throughout the document, affecting readability",
            status="warning",
            confidence=4,
        )

        # Create a format category
        format_category = FormatCategoryItem(
            name="paragraph_spacing",  # Use the string literal directly
            issues=[format_issue],
        )

        # Create a sample review feedback with all required fields
        format_review = FormatReview(
            explanation="The document has some formatting issues that should be addressed",
            categories=[format_category],
            title_issues=[],
            abstract_issues=["Abstract is missing"],
            introduction_issues=[],
            methodology_issues=[],
            results_issues=["Figure 1 is unclear"],
            discussion_issues=[],
            conclusion_issues=[],
            references_issues=["Some references are incomplete"],
            formatting_issues=["Inconsistent spacing"],
            language_issues=["Grammatical errors in paragraph 2"],
            overall_quality="medium",
            summary="The paper needs some improvements in formatting and references.",
        )

        review_state = ReviewState(
            document_images=["mock_image_base64"],
            review_feedback={"vertex_ai": format_review},
            jokes=["Why don't cats play poker in the jungle? Too many cheetahs!"],
        )

        # Return a dictionary containing the ReviewState object under the key "review"
        # This matches the structure expected by the current api.py code: final_state["review"].review_feedback
        return {"review": review_state}


@pytest.fixture
def mock_get_project_id() -> Callable[[], str]:
    """
    Provides a function that returns a mock GCP project ID.

    Returns
    -------
    Callable[[], str]
        A function that returns "mock-project-id".
    """

    def _get_project_id() -> str:
        return "mock-project-id"

    return _get_project_id


@pytest.fixture
def mock_get_location() -> Callable[[], str]:
    """
    Provides a function that returns a mock GCP location.

    Returns
    -------
    Callable[[], str]
        A function that returns "us-central1".
    """

    def _get_location() -> str:
        return "us-central1"

    return _get_location


@pytest.fixture
def review_dependencies(
    mock_get_project_id: Callable[[], str], mock_get_location: Callable[[], str]
) -> ReviewDependencies:
    """
    Provides a ReviewDependencies instance with mock implementations.

    Parameters
    ----------
    mock_get_project_id : Callable[[], str]
        Fixture providing the mock project ID getter function.
    mock_get_location : Callable[[], str]
        Fixture providing the mock location getter function.

    Returns
    -------
    ReviewDependencies
        An instance populated with mock factories and getters.
    """
    return ReviewDependencies(
        review_pdf_factory=MockReviewPDF,
        provider_config_factory=MockVertexAIConfig,
        get_project_id=mock_get_project_id,
        get_location=mock_get_location,
    )


@pytest.fixture
def client(review_dependencies: ReviewDependencies) -> Iterator[TestClient]:
    """
    Provides a TestClient for the FastAPI application with mock dependencies.

    Overrides the `get_review_dependencies` dependency for the duration of the test.

    Parameters
    ----------
    review_dependencies : ReviewDependencies
        Fixture providing the mock dependencies instance.

    Yields
    ------
    TestClient
        A Starlette TestClient configured with mock dependencies.
    """
    app.dependency_overrides[get_review_dependencies] = lambda: review_dependencies
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def mock_review_pdf_run() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Provides a mock function mimicking ReviewPDF._run for unit tests.

    Returns a dictionary structure suitable for direct use in unit test assertions,
    differing slightly from the structure returned by the main MockReviewPDF._run.

    Returns
    -------
    Callable[[Dict[str, Any]], Dict[str, Any]]
        A mock function that accepts a config dict and returns a mock result dict.
    """

    def _mock_run(config: Dict[str, Any]) -> Dict[str, Any]:
        """Mock run implementation for specific unit test needs."""
        # Simulate returning a dictionary structure matching ControlState
        mock_review_data = {
            "review_feedback": {
                "vertex_ai": FormatReview(  # Keep FormatReview object here
                    provider_name="vertex_ai",
                    feedback="Mock feedback",
                    suggestions=["Mock suggestion"],
                )
            },
            "jokes": ["Why don't cats play poker in the jungle? Too many cheetahs!"],
        }
        # Return a dictionary mimicking the structure used in api.py
        return {
            "app_config": ReviewConfig(**config),  # Keep ReviewConfig object
            "review": type(
                "MockReviewState", (), mock_review_data
            )(),  # Create an object-like structure for review
        }

    return _mock_run
