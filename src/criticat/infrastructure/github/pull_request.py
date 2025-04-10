"""
GitHub integration module for Criticat.
Handles GitHub API interactions for PR comments.
"""

import logging

import requests

from criticat.models.models import PRCommentPayload


logger = logging.getLogger(__name__)


def comment_on_pr(payload: PRCommentPayload) -> bool:
    """
    Add a comment to a GitHub pull request using the GitHub API.

    Args:
        payload: PRCommentPayload containing repository, PR number, comment body and token

    Returns:
        True if comment was successfully added, False otherwise
    """
    logger.info(f"Commenting on PR {payload.repository}#{payload.pr_number}")

    url = f"https://api.github.com/repos/{payload.repository}/issues/{payload.pr_number}/comments"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {payload.github_token}",
        "Content-Type": "application/json",
    }
    data = {"body": payload.body}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(
            f"Successfully commented on PR {payload.repository}#{payload.pr_number}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to comment on PR: {e}")
        return False


def format_pr_comment(review_feedback: str, jokes: list[str]) -> str:
    """
    Format a PR comment from review feedback and jokes.

    Args:
        review_feedback: The review feedback text
        jokes: List of joke strings to include

    Returns:
        Formatted PR comment body
    """
    from criticat.infrastructure.llms.prompts import PR_COMMENT_TEMPLATE

    jokes_section = ""
    if jokes:
        jokes_section = "\n### 😹 CritiCat Says\n\n" + "\n".join(
            [f"> {joke}" for joke in jokes]
        )

    return PR_COMMENT_TEMPLATE.format(
        review_feedback=review_feedback, jokes=jokes_section
    )
