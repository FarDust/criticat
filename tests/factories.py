"""Test data builders and fakes shared across the suite."""

from pathlib import Path
from typing import Any, get_args

from PIL import Image, ImageDraw
from pydantic import BaseModel

from criticat.models.formatting import (
    FormatCategoryItem,
    FormatCategoryName,
    FormatIssue,
    FormatReview,
    IssueBoundingBox,
)
from criticat.models.states.review import ReviewState

DEFAULT_JOKE = "Why don't cats play poker in the jungle? Too many cheetahs!"
CATEGORY_NAMES: tuple[str, ...] = get_args(FormatCategoryName)


def make_issue(
    status: str = "warning",
    description: str = "Inconsistent spacing between paragraphs",
    confidence: int = 4,
    example: str = "Experience section",
) -> FormatIssue:
    return FormatIssue(
        description=description,
        explanation="The spacing between paragraphs varies throughout the document",
        error_location=IssueBoundingBox(
            example=example, bounding_box=[50, 120, 550, 180]
        ),
        cause="Inconsistent use of \\vspace between sections",
        status=status,
        confidence=confidence,
    )


def make_feedback(
    *issues: tuple[str, FormatIssue],
    explanation: str = "The document has some formatting issues",
) -> FormatReview:
    by_category: dict[str, list[FormatIssue]] = {}
    for category, issue in issues:
        by_category.setdefault(category, []).append(issue)
    return FormatReview(
        explanation=explanation,
        categories=[
            FormatCategoryItem(name=name, issues=items)
            for name, items in by_category.items()
        ],
    )


def make_review_state(
    feedback: FormatReview | None = None,
    jokes: list[str] | None = None,
    provider: str = "vertex_ai",
) -> ReviewState:
    if feedback is None:
        feedback = make_feedback(("line_spacing", make_issue()))
    return ReviewState(
        document_images=["bW9jaw=="],
        review_feedback={provider: feedback},
        jokes=[DEFAULT_JOKE] if jokes is None else jokes,
    )


def write_pdf(path: Path, pages: int = 2) -> Path:
    """Write a real multi-page PDF that Poppler can render."""
    images = []
    for page in range(pages):
        image = Image.new("RGB", (400, 520), "white")
        ImageDraw.Draw(image).text((40, 40), f"Criticat page {page + 1}", fill="black")
        images.append(image)
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])
    return path


def write_fake_pdf(path: Path) -> Path:
    """Write a file that passes header validation without being renderable."""
    path.write_bytes(b"%PDF-1.4\n%fake\n")
    return path


class FakeReviewRunner:
    def __init__(self, factory: "FakeReviewPDFFactory") -> None:
        self._factory = factory

    def _run(self, config: dict[str, Any]) -> dict[str, Any]:
        self._factory.run_configs.append(config)
        if self._factory.error is not None:
            raise self._factory.error
        return self._factory.result


class FakeReviewPDFFactory:
    """Stand-in for the ``ReviewPDF`` class that records how it was used."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = {"review": make_review_state()} if result is None else result
        self.error = error
        self.provider_configs: list[list[BaseModel]] = []
        self.run_configs: list[dict[str, Any]] = []

    def __call__(self, provider_configs: list[BaseModel]) -> FakeReviewRunner:
        self.provider_configs.append(provider_configs)
        return FakeReviewRunner(self)
