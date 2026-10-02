"""
Integration tests for the REST API running the real dependency container and
LangGraph pipeline, with only the Vertex AI chains replaced by fakes.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from criticat.interfaces.mcp import combined_app
from criticat.use_cases import review as review_module
from tests.conftest import requires_poppler
from tests.factories import make_feedback, make_issue

FEEDBACK = make_feedback(("text_occlusion", make_issue("critical", "Clipped table")))


@pytest.fixture
def chain_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, list[Any]]:
    monkeypatch.chdir(tmp_path)
    calls: dict[str, list[Any]] = {"created": [], "review": [], "joke": []}

    def review_chain(project_id: str, location: str) -> RunnableLambda:
        calls["created"].append((project_id, location))
        return RunnableLambda(lambda inputs: calls["review"].append(inputs) or FEEDBACK)

    def joke_chain(project_id: str, location: str) -> RunnableLambda:
        return RunnableLambda(lambda inputs: calls["joke"].append(inputs) or "Hiss.")

    monkeypatch.setattr(review_module, "review_feedback_chain", review_chain)
    monkeypatch.setattr(review_module, "joke_chain", joke_chain)
    return calls


@pytest.fixture
def real_client() -> Iterator[TestClient]:
    with TestClient(combined_app) as client:
        yield client


def test_health(real_client: TestClient) -> None:
    response = real_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "Criticat API"}


@requires_poppler
def test_full_pipeline_with_real_pdf(
    real_client: TestClient,
    chain_calls: dict[str, list[Any]],
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcloud-project")
    monkeypatch.setenv("CLOUDSDK_COMPUTE_REGION", "europe-west1")

    response = real_client.post(
        "/review", json={"pdf_path": str(sample_pdf), "joke_mode": "default"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["jokes"] == ["Hiss."]
    assert body["review_feedback"]["vertex_ai"] == FEEDBACK.model_dump()
    assert chain_calls["created"] == [("gcloud-project", "europe-west1")]
    assert len(chain_calls["review"][0]["document_images"]) == 2

    report = json.loads((tmp_path / "reports" / "criticat_feedback.json").read_text())
    assert report["jokes"] == ["Hiss."]


def test_missing_project_with_real_container(
    real_client: TestClient, fake_pdf: Path
) -> None:
    response = real_client.post("/review", json={"pdf_path": str(fake_pdf)})
    assert response.status_code == 400
    assert "No GCP project ID provided" in response.json()["detail"]


def test_missing_pdf_with_real_container(
    real_client: TestClient, tmp_path: Path
) -> None:
    response = real_client.post(
        "/review",
        json={"pdf_path": str(tmp_path / "missing.pdf"), "project_id": "p"},
    )
    assert response.status_code == 400


@requires_poppler
def test_unrenderable_pdf_returns_500(
    real_client: TestClient,
    chain_calls: dict[str, list[Any]],
    fake_pdf: Path,
) -> None:
    response = real_client.post(
        "/review", json={"pdf_path": str(fake_pdf), "project_id": "p"}
    )
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Review failed:")
    assert chain_calls["review"] == []


def test_invalid_joke_mode_returns_422(real_client: TestClient, fake_pdf: Path) -> None:
    response = real_client.post(
        "/review", json={"pdf_path": str(fake_pdf), "joke_mode": "invalid_mode"}
    )
    assert response.status_code == 422
