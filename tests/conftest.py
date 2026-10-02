"""
Pytest configuration for Criticat tests.

Contains shared fixtures; every test runs with GCP-related environment
variables cleared so results never depend on the developer's machine.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from criticat.interfaces.api import ReviewDependencies, app, get_review_dependencies
from criticat.models.config import environment
from tests.factories import FakeReviewPDFFactory, write_fake_pdf, write_pdf

GCP_ENV_VARS = (
    "CRITICAT_GCP_PROJECT_ID",
    "CRITICAT_GCP_LOCATION",
    "CLOUDSDK_CORE_PROJECT",
    "GOOGLE_CLOUD_PROJECT",
    "CLOUDSDK_COMPUTE_REGION",
    "CRITICAT_MCP_TRANSPORT",
    "CRITICAT_LOG_LEVEL",
)

requires_poppler = pytest.mark.skipif(
    shutil.which("pdftoppm") is None, reason="Poppler (pdftoppm) is not installed"
)


class MockVertexAIConfig(BaseModel):
    """Mock configuration for Vertex AI LLM provider."""

    llm_provider: str = "vertex_ai"
    project_id: str
    location: str = "us-central1"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in GCP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(environment.settings, "gcp_project_id", None)
    monkeypatch.setattr(environment.settings, "gcp_location", "us-central1")


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return write_pdf(tmp_path / "sample.pdf", pages=2)


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    return write_fake_pdf(tmp_path / "fake.pdf")


@pytest.fixture
def review_factory() -> FakeReviewPDFFactory:
    return FakeReviewPDFFactory()


@pytest.fixture
def review_dependencies(review_factory: FakeReviewPDFFactory) -> ReviewDependencies:
    return ReviewDependencies(
        review_pdf_factory=review_factory,
        provider_config_factory=MockVertexAIConfig,
        get_project_id=lambda: "mock-project-id",
        get_location=lambda: "us-central1",
    )


@pytest.fixture
def override_dependencies(
    review_dependencies: ReviewDependencies,
) -> Iterator[ReviewDependencies]:
    app.dependency_overrides[get_review_dependencies] = lambda: review_dependencies
    yield review_dependencies
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_dependencies: ReviewDependencies) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
