"""Unit tests for the Criticat REST API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from criticat.interfaces.api import ReviewDependencies, app, health_check
from criticat.models.config.app import JokeMode
from tests.conftest import MockVertexAIConfig
from tests.factories import FakeReviewPDFFactory, make_review_state


@pytest.mark.asyncio
async def test_health_check_returns_healthy_status() -> None:
    assert await health_check() == {"status": "healthy", "service": "Criticat API"}


def test_openapi_uses_stable_operation_ids() -> None:
    paths = app.openapi()["paths"]
    assert paths["/review"]["post"]["operationId"] == "review_pdf"
    assert paths["/health"]["get"]["operationId"] == "health_check"


class TestReviewEndpoint:
    def test_returns_review(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        response = client.post(
            "/review",
            json={"pdf_path": str(fake_pdf), "project_id": "p", "joke_mode": "none"},
        )

        assert response.status_code == 200
        expected = make_review_state()
        body = response.json()
        assert body["jokes"] == expected.jokes
        assert body["review_feedback"] == {
            name: feedback.model_dump()
            for name, feedback in expected.review_feedback.items()
        }
        assert "document_images" not in body
        assert review_factory.provider_configs == [
            [MockVertexAIConfig(project_id="p", location="us-central1")]
        ]
        assert review_factory.run_configs == [
            {"pdf_path": str(fake_pdf.resolve()), "joke_mode": JokeMode.NONE}
        ]

    def test_project_and_location_fall_back_to_dependencies(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
        review_dependencies: ReviewDependencies,
    ) -> None:
        review_dependencies.get_location = lambda: "europe-west1"
        response = client.post("/review", json={"pdf_path": str(fake_pdf)})
        assert response.status_code == 200
        assert review_factory.provider_configs == [
            [MockVertexAIConfig(project_id="mock-project-id", location="europe-west1")]
        ]

    def test_explicit_location_wins(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        client.post(
            "/review", json={"pdf_path": str(fake_pdf), "location": "asia-east1"}
        )
        assert review_factory.provider_configs[0][0].location == "asia-east1"

    @pytest.mark.parametrize("mode", list(JokeMode))
    def test_joke_mode_is_forwarded(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
        mode: JokeMode,
    ) -> None:
        response = client.post(
            "/review", json={"pdf_path": str(fake_pdf), "joke_mode": mode.value}
        )
        assert response.status_code == 200
        assert review_factory.run_configs[0]["joke_mode"] is mode

    def test_missing_project_returns_400(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_dependencies: ReviewDependencies,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        review_dependencies.get_project_id = lambda: None
        response = client.post("/review", json={"pdf_path": str(fake_pdf)})
        assert response.status_code == 400
        assert "No GCP project ID provided" in response.json()["detail"]
        assert review_factory.provider_configs == []

    def test_missing_pdf_returns_400(
        self,
        client: TestClient,
        tmp_path: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        response = client.post(
            "/review", json={"pdf_path": str(tmp_path / "missing.pdf")}
        )
        assert response.status_code == 400
        assert "PDF file not found" in response.json()["detail"]
        assert review_factory.provider_configs == []

    def test_non_pdf_returns_400(self, client: TestClient, tmp_path: Path) -> None:
        path = tmp_path / "paper.pdf"
        path.write_text("not a pdf")
        response = client.post("/review", json={"pdf_path": str(path)})
        assert response.status_code == 400
        assert "does not look like a PDF" in response.json()["detail"]

    def test_invalid_joke_mode_returns_422(
        self, client: TestClient, fake_pdf: Path
    ) -> None:
        response = client.post(
            "/review", json={"pdf_path": str(fake_pdf), "joke_mode": "loud"}
        )
        assert response.status_code == 422
        assert any("joke_mode" in error["loc"] for error in response.json()["detail"])

    def test_missing_pdf_path_returns_422(self, client: TestClient) -> None:
        assert client.post("/review", json={}).status_code == 422

    def test_pipeline_failure_returns_500(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        review_factory.error = RuntimeError("quota exceeded")
        response = client.post("/review", json={"pdf_path": str(fake_pdf)})
        assert response.status_code == 500
        assert response.json()["detail"] == "Review failed: quota exceeded"

    def test_missing_review_state_returns_500(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        review_factory.result = {}
        response = client.post("/review", json={"pdf_path": str(fake_pdf)})
        assert response.status_code == 500

    def test_accepts_review_state_as_dict(
        self,
        client: TestClient,
        fake_pdf: Path,
        review_factory: FakeReviewPDFFactory,
    ) -> None:
        review_factory.result = {"review": make_review_state(jokes=["x"]).model_dump()}
        response = client.post("/review", json={"pdf_path": str(fake_pdf)})
        assert response.status_code == 200
        assert response.json()["jokes"] == ["x"]
