"""Tests for configuration, environment resolution and formatting models."""

import pytest
from pydantic import ValidationError

from criticat.models.config import environment
from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.config.environment import (
    CriticatSettings,
    get_gcp_location,
    get_gcp_project_id,
)
from criticat.models.formatting import FormatReview
from criticat.models.models import VertexAIConfig
from tests.factories import make_feedback, make_issue


class TestGcpProjectId:
    def test_none_when_unset(self) -> None:
        assert get_gcp_project_id() is None

    def test_criticat_setting_has_priority(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(environment.settings, "gcp_project_id", "criticat")
        monkeypatch.setenv("CLOUDSDK_CORE_PROJECT", "cloudsdk")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "google")
        assert get_gcp_project_id() == "criticat"

    def test_cloudsdk_before_google_cloud(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLOUDSDK_CORE_PROJECT", "cloudsdk")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "google")
        assert get_gcp_project_id() == "cloudsdk"

    def test_google_cloud_project_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "google")
        assert get_gcp_project_id() == "google"


class TestGcpLocation:
    def test_default_location(self) -> None:
        assert get_gcp_location() == "us-central1"

    def test_cloudsdk_region_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLOUDSDK_COMPUTE_REGION", "europe-west4")
        assert get_gcp_location() == "europe-west4"

    def test_explicit_setting_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(environment.settings, "gcp_location", "asia-east1")
        monkeypatch.setenv("CLOUDSDK_COMPUTE_REGION", "europe-west4")
        assert get_gcp_location() == "asia-east1"


class TestCriticatSettings:
    def test_reads_prefixed_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRITICAT_GCP_PROJECT_ID", "from-env")
        monkeypatch.setenv("CRITICAT_SERVER_PORT", "9001")
        settings = CriticatSettings()
        assert settings.gcp_project_id == "from-env"
        assert settings.server_port == 9001

    def test_reads_envrc_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".envrc").write_text("CRITICAT_GCP_LOCATION=me-west1\n")
        assert CriticatSettings().gcp_location == "me-west1"


class TestConfigModels:
    def test_review_config_defaults(self) -> None:
        config = ReviewConfig(pdf_path="doc.pdf")
        assert config.joke_mode is JokeMode.DEFAULT

    def test_review_config_rejects_unknown_joke_mode(self) -> None:
        with pytest.raises(ValidationError):
            ReviewConfig(pdf_path="doc.pdf", joke_mode="loud")

    def test_vertex_config_defaults(self) -> None:
        config = VertexAIConfig(project_id="p")
        assert config.llm_provider == "vertex_ai"
        assert config.location == "us-central1"


class TestFormatReview:
    @pytest.mark.parametrize(
        ("status", "blocking"),
        [("critical", True), ("error", True), ("warning", False), ("info", False)],
    )
    def test_has_issues_only_for_blocking_statuses(
        self, status: str, blocking: bool
    ) -> None:
        feedback = make_feedback(("line_spacing", make_issue(status)))
        assert feedback.has_issues() is blocking

    def test_issue_count(self) -> None:
        feedback = make_feedback(
            ("line_spacing", make_issue()),
            ("line_spacing", make_issue()),
            ("font_quality", make_issue()),
        )
        assert feedback.issue_count() == 3

    def test_empty_review(self) -> None:
        feedback = FormatReview(explanation="clean", categories=[])
        assert feedback.has_issues() is False
        assert feedback.issue_count() == 0

    @pytest.mark.parametrize("confidence", [0, 6])
    def test_confidence_bounds(self, confidence: int) -> None:
        with pytest.raises(ValidationError):
            make_issue(confidence=confidence)

    def test_rejects_unknown_category(self) -> None:
        with pytest.raises(ValidationError):
            make_feedback(("paragraph_spacing", make_issue()))
