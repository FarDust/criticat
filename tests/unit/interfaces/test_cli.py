"""Tests for the Typer CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from criticat.interfaces import cli
from criticat.models.config.app import JokeMode
from criticat.models.models import VertexAIConfig
from criticat.use_cases.service import ReviewService
from tests.factories import FakeReviewPDFFactory

runner = CliRunner()


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> FakeReviewPDFFactory:
    fake = FakeReviewPDFFactory()
    monkeypatch.setattr(
        cli, "ReviewService", lambda: ReviewService(review_pdf_factory=fake)
    )
    return fake


def test_review_prints_markdown_report(
    factory: FakeReviewPDFFactory, fake_pdf: Path
) -> None:
    result = runner.invoke(
        cli.app,
        [
            "--pdf-path",
            str(fake_pdf),
            "--project-id",
            "proj",
            "--location",
            "europe-west1",
            "--joke-mode",
            "chaotic",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Criticat Document Review" in result.output
    assert factory.provider_configs == [
        [VertexAIConfig(project_id="proj", location="europe-west1")]
    ]
    assert factory.run_configs[0]["joke_mode"] is JokeMode.CHAOTIC


def test_project_id_from_env(
    factory: FakeReviewPDFFactory,
    fake_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRITICAT_GCP_PROJECT_ID", "env-proj")
    result = runner.invoke(cli.app, ["--pdf-path", str(fake_pdf)])
    assert result.exit_code == 0, result.output
    assert factory.provider_configs[0][0].project_id == "env-proj"


def test_project_id_from_google_cloud_env(
    factory: FakeReviewPDFFactory,
    fake_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcloud-proj")
    result = runner.invoke(cli.app, ["--pdf-path", str(fake_pdf)])
    assert result.exit_code == 0, result.output
    assert factory.provider_configs[0][0].project_id == "gcloud-proj"


def test_missing_project_exits_1(factory: FakeReviewPDFFactory, fake_pdf: Path) -> None:
    result = runner.invoke(cli.app, ["--pdf-path", str(fake_pdf)])
    assert result.exit_code == 1
    assert factory.provider_configs == []


def test_missing_pdf_exits_1(factory: FakeReviewPDFFactory, tmp_path: Path) -> None:
    result = runner.invoke(
        cli.app, ["--pdf-path", str(tmp_path / "nope.pdf"), "--project-id", "p"]
    )
    assert result.exit_code == 1
    assert factory.provider_configs == []


def test_pipeline_failure_exits_1(
    factory: FakeReviewPDFFactory, fake_pdf: Path
) -> None:
    factory.error = RuntimeError("boom")
    result = runner.invoke(cli.app, ["--pdf-path", str(fake_pdf), "--project-id", "p"])
    assert result.exit_code == 1


def test_invalid_joke_mode_is_usage_error(fake_pdf: Path) -> None:
    result = runner.invoke(
        cli.app, ["--pdf-path", str(fake_pdf), "--joke-mode", "loud"]
    )
    assert result.exit_code == 2


def test_requires_pdf_path() -> None:
    assert runner.invoke(cli.app, []).exit_code == 2
