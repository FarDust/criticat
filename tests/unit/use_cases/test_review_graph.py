"""Tests for the ReviewPDF LangGraph workflow with fake LLM chains."""

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.formatting import FormatReview
from criticat.models.models import VertexAIConfig
from criticat.models.states.review import ReviewState
from criticat.use_cases import review as review_module
from criticat.use_cases.review import ReviewPDF
from tests.conftest import requires_poppler
from tests.factories import make_feedback, make_issue


class FakeChains:
    def __init__(self, feedback: FormatReview) -> None:
        self.feedback = feedback
        self.review_inputs: list[dict[str, Any]] = []
        self.joke_inputs: list[dict[str, Any]] = []
        self.created_with: list[tuple[str, str]] = []

    def review_chain(self, project_id: str, location: str) -> RunnableLambda:
        self.created_with.append((project_id, location))

        def run(inputs: dict[str, Any]) -> FormatReview:
            self.review_inputs.append(inputs)
            return self.feedback

        return RunnableLambda(run)

    def joke_chain(self, project_id: str, location: str) -> RunnableLambda:
        def run(inputs: dict[str, Any]) -> str:
            self.joke_inputs.append(inputs)
            return f"joke #{len(self.joke_inputs)}"

        return RunnableLambda(run)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def install_chains(
    monkeypatch: pytest.MonkeyPatch, feedback: FormatReview
) -> FakeChains:
    chains = FakeChains(feedback)
    monkeypatch.setattr(review_module, "review_feedback_chain", chains.review_chain)
    monkeypatch.setattr(review_module, "joke_chain", chains.joke_chain)
    return chains


def run_review(pdf_path: str, joke_mode: JokeMode = JokeMode.DEFAULT) -> dict[str, Any]:
    use_case = ReviewPDF(
        provider_configs=[VertexAIConfig(project_id="proj", location="loc")]
    )
    return use_case._run(
        config=ReviewConfig(pdf_path=pdf_path, joke_mode=joke_mode).model_dump()
    )


@pytest.fixture
def fake_pages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    pages = ["cGFnZTE=", "cGFnZTI="]
    calls: list[str] = []

    def extract(pdf_path: str) -> list[str]:
        calls.append(pdf_path)
        return pages

    monkeypatch.setattr(review_module, "extract_document_image", extract)
    return pages


blocking = make_feedback(("text_occlusion", make_issue("critical")))
cosmetic = make_feedback(("line_spacing", make_issue("info")))


def test_creates_chains_from_vertex_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chains = install_chains(monkeypatch, cosmetic)
    ReviewPDF(provider_configs=[VertexAIConfig(project_id="proj", location="loc")])
    assert chains.created_with == [("proj", "loc")]


def test_graph_runs_review_with_extracted_pages(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    chains = install_chains(monkeypatch, blocking)

    final_state = run_review("doc.pdf")

    review = ReviewState.model_validate(final_state["review"], from_attributes=True)
    assert review.document_images == fake_pages
    assert review.review_feedback == {"vertex_ai": blocking}
    assert chains.review_inputs == [{"document_images": fake_pages}]


def test_default_mode_jokes_only_for_blocking_issues(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    chains = install_chains(monkeypatch, blocking)
    final_state = run_review("doc.pdf", JokeMode.DEFAULT)
    assert final_state["review"].jokes == ["joke #1"]
    assert chains.joke_inputs == [{"review_feedback": blocking}]


def test_default_mode_no_joke_for_cosmetic_issues(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    install_chains(monkeypatch, cosmetic)
    assert run_review("doc.pdf", JokeMode.DEFAULT)["review"].jokes == []


def test_none_mode_never_jokes(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    chains = install_chains(monkeypatch, blocking)
    assert run_review("doc.pdf", JokeMode.NONE)["review"].jokes == []
    assert chains.joke_inputs == []


@pytest.mark.parametrize("count", [1, 3])
def test_chaotic_mode_adds_random_number_of_jokes(
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
    fake_pages: list[str],
    count: int,
) -> None:
    install_chains(monkeypatch, cosmetic)
    monkeypatch.setattr(review_module.random, "randint", lambda a, b: count)
    jokes = run_review("doc.pdf", JokeMode.CHAOTIC)["review"].jokes
    assert jokes == [f"joke #{i + 1}" for i in range(count)]


def test_writes_report_without_images(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    install_chains(monkeypatch, blocking)
    run_review("doc.pdf")

    report = json.loads((workdir / "reports" / "criticat_feedback.json").read_text())
    assert "document_images" not in report
    assert report["jokes"] == ["joke #1"]
    assert ReviewState.model_validate(report).review_feedback == {"vertex_ai": blocking}


def test_skips_pr_comment_without_git_provider(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, fake_pages: list[str]
) -> None:
    install_chains(monkeypatch, cosmetic)
    called: list[object] = []
    monkeypatch.setattr(
        ReviewPDF, "comment_pr_node", lambda self, state: called.append(state)
    )
    run_review("doc.pdf")
    assert called == []


def test_extraction_errors_propagate(
    monkeypatch: pytest.MonkeyPatch, workdir: Path
) -> None:
    install_chains(monkeypatch, cosmetic)

    def broken(pdf_path: str) -> list[str]:
        raise ValueError("No images extracted from PDF")

    monkeypatch.setattr(review_module, "extract_document_image", broken)
    with pytest.raises(ValueError, match="No images extracted"):
        run_review("doc.pdf")


@requires_poppler
def test_end_to_end_with_real_pdf(
    monkeypatch: pytest.MonkeyPatch, workdir: Path, sample_pdf: Path
) -> None:
    chains = install_chains(monkeypatch, cosmetic)
    review = run_review(str(sample_pdf), JokeMode.NONE)["review"]
    assert len(review.document_images) == 2
    assert len(chains.review_inputs[0]["document_images"]) == 2
