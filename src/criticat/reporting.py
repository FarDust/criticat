"""
Summaries and Markdown rendering for review results.
"""

from typing import Literal

from pydantic import BaseModel, Field

from criticat.models.formatting import FormatReview
from criticat.models.states.review import ReviewState

IssueStatus = Literal["critical", "error", "warning", "info"]
STATUS_ORDER: tuple[IssueStatus, ...] = ("critical", "error", "warning", "info")
STATUS_ICONS: dict[str, str] = {
    "critical": "🔴",
    "error": "🟠",
    "warning": "🟡",
    "info": "🔵",
}


class ReviewSummary(BaseModel):
    issue_count: int = Field(description="Total number of issues across providers")
    issues_by_status: dict[str, int] = Field(
        description="Issue counts keyed by status (critical, error, warning, info)"
    )
    has_blocking_issues: bool = Field(
        description="True when at least one critical or error issue was found"
    )
    providers: list[str] = Field(description="Providers that produced feedback")


def summarize_review(review: ReviewState) -> ReviewSummary:
    counts = dict.fromkeys(STATUS_ORDER, 0)
    for feedback in review.review_feedback.values():
        for category in feedback.categories:
            for issue in category.issues:
                counts[issue.status] += 1
    return ReviewSummary(
        issue_count=sum(counts.values()),
        issues_by_status=counts,
        has_blocking_issues=any(
            feedback.has_issues() for feedback in review.review_feedback.values()
        ),
        providers=sorted(review.review_feedback),
    )


def _render_feedback(provider: str, feedback: FormatReview) -> list[str]:
    lines = [f"### {provider}", ""]
    if feedback.explanation:
        lines += [feedback.explanation, ""]
    issues = [
        (category.name, issue)
        for category in feedback.categories
        for issue in category.issues
    ]
    if not issues:
        return [*lines, "No formatting issues found.", ""]

    issues.sort(key=lambda item: STATUS_ORDER.index(item[1].status))
    for category_name, issue in issues:
        icon = STATUS_ICONS[issue.status]
        lines.append(
            f"- {icon} **{issue.status.upper()}** `{category_name}`: "
            f"{issue.description} (confidence {issue.confidence}/5)"
        )
        lines.append(f"  - Likely cause: {issue.cause}")
        if issue.error_location.example:
            lines.append(f"  - Example: {issue.error_location.example}")
    lines.append("")
    return lines


def render_review_markdown(review: ReviewState) -> str:
    summary = summarize_review(review)
    counts = ", ".join(
        f"{summary.issues_by_status[status]} {status}" for status in STATUS_ORDER
    )
    lines = [
        "## 😼 Criticat Document Review",
        "",
        f"**{summary.issue_count} issue(s)** ({counts}).",
        "",
    ]
    if not review.review_feedback:
        lines += ["No reviewer feedback was produced.", ""]
    for provider in summary.providers:
        lines += _render_feedback(provider, review.review_feedback[provider])
    if review.jokes:
        lines += ["### 😹 Criticat Says", ""]
        lines += [f"> {joke}" for joke in review.jokes]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
