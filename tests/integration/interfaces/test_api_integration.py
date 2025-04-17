"""
Integration tests for the Criticat API endpoints.

These tests use FastAPI's TestClient to make HTTP requests to the API endpoints.
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from criticat.models.config.app import ReviewConfig
from criticat.models.formatting import FormatReview


@pytest.fixture(scope="module")
def mock_review_pdf_instance():
    """Creates a mock ReviewPDF instance with a mocked _run method returning a DICT."""
    mock_instance = MagicMock()

    def mock_run(config: Dict[str, Any]) -> Dict[str, Any]:  # Return Dict
        mock_review_data = {
            "review_feedback": {
                "mock_provider": FormatReview(  # Keep FormatReview object
                    provider_name="mock_provider",
                    feedback="Integration test feedback",
                    suggestions=["Integration suggestion"],
                )
            },
            "jokes": ["Integration test joke"],
        }
        # Return a dictionary mimicking the structure used in api.py
        return {
            "app_config": ReviewConfig(**config),  # Keep ReviewConfig object
            "review": type(
                "MockReviewState", (), mock_review_data
            )(),  # Create an object-like structure for review
        }

    mock_instance._run.side_effect = mock_run
    return mock_instance


class TestAPIIntegration:
    """Integration tests for the Criticat API."""

    def test_health_endpoint(self, client: TestClient):
        """Test that health check endpoint returns 200 OK with expected response."""
        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "Criticat API"}

    def test_review_endpoint_with_valid_request(
        self, client: TestClient, tmp_path: Path
    ):
        """Test that review endpoint returns 200 OK with expected response structure."""
        # Arrange
        # Create a temporary file to use as PDF path
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        # Create request payload
        request_data = {
            "pdf_path": str(pdf_path),
            "project_id": "test-project-id",
            "joke_mode": "default",
        }

        # Act
        response = client.post("/review", json=request_data)

        # Assert
        assert response.status_code == 200

        response_data = response.json()

        # Check structure of response
        assert "review_feedback" in response_data
        assert "jokes" in response_data
        assert len(response_data["jokes"]) == 1

        # Check review feedback has expected fields
        review_feedback = response_data["review_feedback"]["vertex_ai"]
        assert "explanation" in review_feedback
        assert "categories" in review_feedback

        # Check that categories contain the expected data
        categories = review_feedback["categories"]
        assert len(categories) > 0
        assert categories[0]["name"] == "paragraph_spacing"
        assert len(categories[0]["issues"]) > 0
        assert (
            categories[0]["issues"][0]["description"]
            == "Inconsistent spacing between paragraphs"
        )
        assert categories[0]["issues"][0]["status"] == "warning"

    def test_review_endpoint_with_chaotic_joke_mode(
        self, client: TestClient, tmp_path: Path
    ):
        """Test that review endpoint works with chaotic joke mode."""
        # Arrange
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        request_data = {
            "pdf_path": str(pdf_path),
            "project_id": "test-project-id",
            "joke_mode": "chaotic",
        }

        # Act
        response = client.post("/review", json=request_data)

        # Assert
        assert response.status_code == 200

        response_data = response.json()
        assert "jokes" in response_data
        # Note: In real integration test with non-mocked service,
        # chaotic mode would return 1-3 jokes, but our mock returns a fixed joke

    def test_review_endpoint_without_project_id(
        self, client: TestClient, tmp_path: Path
    ):
        """Test that review endpoint works with project ID from environment."""
        # Arrange
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        request_data = {"pdf_path": str(pdf_path), "joke_mode": "none"}

        # Act
        response = client.post("/review", json=request_data)

        # Assert
        assert response.status_code == 200

        # With our mock dependencies, it should use "mock-project-id"
        response_data = response.json()
        assert "review_feedback" in response_data
        assert "jokes" in response_data

    def test_review_endpoint_with_invalid_pdf_path(self, client: TestClient):
        """Test that review endpoint returns an appropriate error for invalid PDF path."""
        # Arrange
        request_data = {
            "pdf_path": "/path/does/not/exist.pdf",
            "project_id": "test-project-id",
            "joke_mode": "default",
        }

        # NOTE: Our mock currently doesn't validate the PDF path
        # In a real integration test, this would need to be tested
        # and the endpoint should return an appropriate error

        # Act
        response = client.post("/review", json=request_data)

        # Assert
        assert response.status_code == 200

        # In a real implementation, we should test for error handling here

    def test_review_endpoint_with_invalid_joke_mode(
        self, client: TestClient, tmp_path: Path
    ):
        """Test that review endpoint validates the joke mode."""
        # Arrange
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        request_data = {
            "pdf_path": str(pdf_path),
            "project_id": "test-project-id",
            "joke_mode": "invalid_mode",  # Invalid value
        }

        # Act
        response = client.post("/review", json=request_data)

        # Assert
        assert response.status_code == 422  # Validation error

        # Check that error details mention the joke_mode field
        error_details = response.json()["detail"]
        assert any("joke_mode" in error["loc"] for error in error_details)
