"""Tests for the interface-agnostic ReviewService."""

from pathlib import Path

import pytest

from criticat.models.config.app import JokeMode
from criticat.models.models import VertexAIConfig
from criticat.models.states.review import ReviewState
from criticat.use_cases.service import (
    ReviewExecutionError,
    ReviewInputError,
    ReviewService,
    resolve_joke_mode,
    validate_pdf_path,
)
from tests.factories import FakeReviewPDFFactory, make_review_state


def make_service(
    factory: FakeReviewPDFFactory,
    project_id: str | None = "env-project",
    location: str = "europe-west1",
) -> ReviewService:
    return ReviewService(
        review_pdf_factory=factory,
        project_id_resolver=lambda: project_id,
        location_resolver=lambda: location,
    )


class TestValidatePdfPath:
    def test_returns_resolved_path(self, fake_pdf: Path) -> None:
        assert validate_pdf_path(str(fake_pdf)) == fake_pdf.resolve()

    def test_strips_whitespace(self, fake_pdf: Path) -> None:
        assert validate_pdf_path(f"  {fake_pdf}  ") == fake_pdf.resolve()

    def test_expands_user_home(
        self, fake_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(fake_pdf.parent))
        assert validate_pdf_path(f"~/{fake_pdf.name}") == fake_pdf.resolve()

    def test_accepts_uppercase_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "REPORT.PDF"
        path.write_bytes(b"%PDF-1.7\n")
        assert validate_pdf_path(str(path)) == path.resolve()

    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_empty(self, value: str) -> None:
        with pytest.raises(ReviewInputError, match="must not be empty"):
            validate_pdf_path(value)

    def test_rejects_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ReviewInputError, match="not found"):
            validate_pdf_path(str(tmp_path / "missing.pdf"))

    def test_rejects_directory(self, tmp_path: Path) -> None:
        directory = tmp_path / "folder.pdf"
        directory.mkdir()
        with pytest.raises(ReviewInputError, match="not a file"):
            validate_pdf_path(str(directory))

    def test_rejects_wrong_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "paper.tex"
        path.write_bytes(b"%PDF-1.4\n")
        with pytest.raises(ReviewInputError, match=r"Expected a \.pdf file"):
            validate_pdf_path(str(path))

    def test_rejects_non_pdf_content(self, tmp_path: Path) -> None:
        path = tmp_path / "renamed.pdf"
        path.write_text("\\documentclass{article}")
        with pytest.raises(ReviewInputError, match="does not look like a PDF"):
            validate_pdf_path(str(path))

    def test_rejects_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.pdf"
        path.touch()
        with pytest.raises(ReviewInputError, match="does not look like a PDF"):
            validate_pdf_path(str(path))

    def test_input_error_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_pdf_path("")


class TestResolveJokeMode:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("none", JokeMode.NONE),
            ("default", JokeMode.DEFAULT),
            ("CHAOTIC", JokeMode.CHAOTIC),
            (" Default ", JokeMode.DEFAULT),
            (JokeMode.NONE, JokeMode.NONE),
        ],
    )
    def test_valid_modes(self, value: str | JokeMode, expected: JokeMode) -> None:
        assert resolve_joke_mode(value) is expected

    def test_invalid_mode_lists_options(self) -> None:
        with pytest.raises(ReviewInputError, match="none, default, chaotic"):
            resolve_joke_mode("purr")


class TestConfigurationResolution:
    def test_explicit_project_wins(self) -> None:
        service = make_service(FakeReviewPDFFactory())
        assert service.resolve_project_id("explicit") == "explicit"

    def test_falls_back_to_environment_project(self) -> None:
        service = make_service(FakeReviewPDFFactory())
        assert service.resolve_project_id(None) == "env-project"
        assert service.resolve_project_id("   ") == "env-project"

    def test_missing_project_raises(self) -> None:
        service = make_service(FakeReviewPDFFactory(), project_id=None)
        with pytest.raises(ReviewInputError, match="No GCP project ID provided"):
            service.resolve_project_id(None)

    def test_location_explicit_and_fallback(self) -> None:
        service = make_service(FakeReviewPDFFactory())
        assert service.resolve_location("asia-east1") == "asia-east1"
        assert service.resolve_location(None) == "europe-west1"
        assert service.resolve_location("") == "europe-west1"

    def test_default_resolvers_use_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcloud-project")
        monkeypatch.setenv("CLOUDSDK_COMPUTE_REGION", "us-east4")
        service = ReviewService(review_pdf_factory=FakeReviewPDFFactory())
        assert service.resolve_project_id() == "gcloud-project"
        assert service.resolve_location() == "us-east4"


class TestPrepare:
    def test_builds_review_and_provider_config(self, fake_pdf: Path) -> None:
        prepared = make_service(FakeReviewPDFFactory()).prepare(
            pdf_path=str(fake_pdf), joke_mode="chaotic"
        )
        assert prepared.config.pdf_path == str(fake_pdf.resolve())
        assert prepared.config.joke_mode is JokeMode.CHAOTIC
        assert prepared.provider_config == VertexAIConfig(
            project_id="env-project", location="europe-west1"
        )

    def test_validates_path_before_project(self, tmp_path: Path) -> None:
        service = make_service(FakeReviewPDFFactory(), project_id=None)
        with pytest.raises(ReviewInputError, match="not found"):
            service.prepare(pdf_path=str(tmp_path / "nope.pdf"))


class TestRun:
    def test_passes_configuration_to_use_case(self, fake_pdf: Path) -> None:
        factory = FakeReviewPDFFactory()
        review = make_service(factory).run(
            pdf_path=str(fake_pdf),
            project_id="p",
            location="l",
            joke_mode=JokeMode.NONE,
        )

        assert review == make_review_state()
        assert factory.provider_configs == [
            [VertexAIConfig(project_id="p", location="l")]
        ]
        assert factory.run_configs == [
            {"pdf_path": str(fake_pdf.resolve()), "joke_mode": JokeMode.NONE}
        ]

    def test_accepts_review_as_dict(self, fake_pdf: Path) -> None:
        state = make_review_state()
        factory = FakeReviewPDFFactory(result={"review": state.model_dump()})
        assert make_service(factory).run(pdf_path=str(fake_pdf)) == state

    def test_missing_review_state(self, fake_pdf: Path) -> None:
        factory = FakeReviewPDFFactory(result={"app_config": {}})
        with pytest.raises(ReviewExecutionError, match="no 'review' state"):
            make_service(factory).run(pdf_path=str(fake_pdf))

    def test_invalid_review_state(self, fake_pdf: Path) -> None:
        factory = FakeReviewPDFFactory(
            result={"review": {"review_feedback": {"x": {"explanation": "?"}}}}
        )
        with pytest.raises(ReviewExecutionError, match="invalid review state"):
            make_service(factory).run(pdf_path=str(fake_pdf))

    def test_wraps_pipeline_errors(self, fake_pdf: Path) -> None:
        factory = FakeReviewPDFFactory(error=RuntimeError("vertex exploded"))
        with pytest.raises(ReviewExecutionError, match="vertex exploded") as info:
            make_service(factory).run(pdf_path=str(fake_pdf))
        assert isinstance(info.value.__cause__, RuntimeError)

    def test_wraps_factory_errors(self, fake_pdf: Path) -> None:
        def broken_factory(provider_configs: list) -> None:
            raise PermissionError("no credentials")

        service = ReviewService(
            review_pdf_factory=broken_factory,
            project_id_resolver=lambda: "p",
            location_resolver=lambda: "l",
        )
        with pytest.raises(ReviewExecutionError, match="no credentials"):
            service.run(pdf_path=str(fake_pdf))

    def test_input_errors_skip_use_case(self, tmp_path: Path) -> None:
        factory = FakeReviewPDFFactory()
        with pytest.raises(ReviewInputError):
            make_service(factory).run(pdf_path=str(tmp_path / "x.pdf"))
        assert factory.provider_configs == []

    def test_returns_review_state_type(self, fake_pdf: Path) -> None:
        review = make_service(FakeReviewPDFFactory()).run(pdf_path=str(fake_pdf))
        assert isinstance(review, ReviewState)
