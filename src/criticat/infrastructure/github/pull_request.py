"""
GitHub integration module for Criticat.
Handles GitHub API interactions for PR comments.
"""

from logging import getLogger, Logger

import requests

from criticat.infrastructure.github.config import GithubConfig
from pydantic import BaseModel, PrivateAttr
from criticat.infrastructure.github.dtos.pull_request import PRCommentPayload


class PullRequestService(BaseModel):
    config: GithubConfig
    _logger: Logger = PrivateAttr(default=getLogger(__name__))

    def comment_on_pr(self, payload: PRCommentPayload) -> bool:
        """
        Add a comment to a GitHub pull request using the GitHub API.

        Args:
            payload: PRCommentPayload containing repository, PR number, comment body and token

        Returns:
            True if comment was successfully added, False otherwise
        """
        self._logger.info(f"Commenting on PR {payload.repository}#{payload.pr_number}")

        url = f"https://api.github.com/repos/{payload.repository}/issues/{payload.pr_number}/comments"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.config.github_token}",
            "Content-Type": "application/json",
        }
        data = {"body": payload.body}

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            self._logger.info(
                f"Successfully commented on PR {payload.repository}#{payload.pr_number}"
            )
            return True
        except Exception as e:
            self._logger.error(f"Failed to comment on PR: {e}")
            return False

    def format_pr_comment(self, review_feedback: str, jokes: list[str]) -> str:
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
