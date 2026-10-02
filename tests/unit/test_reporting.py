"""Tests for review summaries and Markdown rendering."""

from criticat.models.states.review import ReviewState
from criticat.reporting import render_review_markdown, summarize_review
from tests.factories import make_feedback, make_issue, make_review_state


def mixed_review() -> ReviewState:
    feedback = make_feedback(
        ("line_spacing", make_issue("warning", "Uneven spacing")),
        ("text_occlusion", make_issue("critical", "Figure covers text")),
        ("line_spacing", make_issue("info", "Slightly tight", example="")),
        ("font_quality", make_issue("error", "Blurry font")),
    )
    return make_review_state(feedback=feedback, jokes=["Meow.", "Hiss."])


class TestSummarizeReview:
    def test_counts_by_status(self) -> None:
        summary = summarize_review(mixed_review())
        assert summary.issue_count == 4
        assert summary.issues_by_status == {
            "critical": 1,
            "error": 1,
            "warning": 1,
            "info": 1,
        }
        assert summary.has_blocking_issues is True
        assert summary.providers == ["vertex_ai"]

    def test_non_blocking_review(self) -> None:
        summary = summarize_review(make_review_state())
        assert summary.issue_count == 1
        assert summary.has_blocking_issues is False

    def test_empty_review(self) -> None:
        summary = summarize_review(ReviewState())
        assert summary.issue_count == 0
        assert summary.has_blocking_issues is False
        assert summary.providers == []

    def test_aggregates_multiple_providers(self) -> None:
        review = ReviewState(
            review_feedback={
                "b": make_feedback(("line_spacing", make_issue("error"))),
                "a": make_feedback(("line_spacing", make_issue("info"))),
            }
        )
        summary = summarize_review(review)
        assert summary.issue_count == 2
        assert summary.providers == ["a", "b"]
        assert summary.has_blocking_issues is True


class TestRenderReviewMarkdown:
    def test_orders_issues_by_severity(self) -> None:
        markdown = render_review_markdown(mixed_review())
        positions = [
            markdown.index(label) for label in ("CRITICAL", "ERROR", "WARNING", "INFO")
        ]
        assert positions == sorted(positions)

    def test_includes_header_counts_and_details(self) -> None:
        markdown = render_review_markdown(mixed_review())
        assert markdown.startswith("## 😼 Criticat Document Review")
        assert "**4 issue(s)** (1 critical, 1 error, 1 warning, 1 info)." in markdown
        assert "`text_occlusion`: Figure covers text (confidence 4/5)" in markdown
        assert "Likely cause: Inconsistent use of \\vspace" in markdown
        assert "Example: Experience section" in markdown

    def test_omits_empty_examples(self) -> None:
        markdown = render_review_markdown(mixed_review())
        info_block = markdown[markdown.index("INFO") :]
        assert "Example:" not in info_block.split("\n- ")[0]

    def test_renders_jokes(self) -> None:
        markdown = render_review_markdown(mixed_review())
        assert "### 😹 Criticat Says" in markdown
        assert "> Meow.\n> Hiss." in markdown

    def test_no_jokes_section_without_jokes(self) -> None:
        markdown = render_review_markdown(make_review_state(jokes=[]))
        assert "Criticat Says" not in markdown

    def test_clean_document(self) -> None:
        review = make_review_state(feedback=make_feedback(), jokes=[])
        markdown = render_review_markdown(review)
        assert "No formatting issues found." in markdown
        assert "**0 issue(s)**" in markdown

    def test_no_feedback(self) -> None:
        assert "No reviewer feedback was produced." in render_review_markdown(
            ReviewState()
        )

    def test_ends_with_single_newline(self) -> None:
        markdown = render_review_markdown(mixed_review())
        assert markdown.endswith("\n")
        assert not markdown.endswith("\n\n")
