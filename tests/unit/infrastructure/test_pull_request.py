"""Tests for the GitHub pull request service."""

from typing import Any

import pytest
import requests

from criticat.infrastructure.github import pull_request
from criticat.infrastructure.github.config import GithubConfig
from criticat.infrastructure.github.dtos.pull_request import PRCommentPayload
from criticat.infrastructure.github.pull_request import PullRequestService


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


@pytest.fixture
def service() -> PullRequestService:
    return PullRequestService(
        config=GithubConfig(github_token="ghp_secret", repository="owner/repo")
    )


@pytest.fixture
def payload() -> PRCommentPayload:
    return PRCommentPayload(repository="owner/repo", pr_number=7, body="Meow")


def capture_post(
    monkeypatch: pytest.MonkeyPatch, status_code: int = 201
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return FakeResponse(status_code)

    monkeypatch.setattr(pull_request.requests, "post", fake_post)
    return calls


def test_comment_on_pr_posts_to_issue_comments(
    monkeypatch: pytest.MonkeyPatch,
    service: PullRequestService,
    payload: PRCommentPayload,
) -> None:
    calls = capture_post(monkeypatch)

    assert service.comment_on_pr(payload) is True
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://api.github.com/repos/owner/repo/issues/7/comments"
    assert call["json"] == {"body": "Meow"}
    assert call["headers"]["Authorization"] == "token ghp_secret"
    assert call["headers"]["Accept"] == "application/vnd.github.v3+json"


def test_comment_on_pr_returns_false_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
    service: PullRequestService,
    payload: PRCommentPayload,
) -> None:
    capture_post(monkeypatch, status_code=403)
    assert service.comment_on_pr(payload) is False


def test_comment_on_pr_returns_false_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
    service: PullRequestService,
    payload: PRCommentPayload,
) -> None:
    def fail(url: str, **kwargs: Any) -> FakeResponse:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(pull_request.requests, "post", fail)
    assert service.comment_on_pr(payload) is False


def test_format_pr_comment_with_jokes(service: PullRequestService) -> None:
    body = service.format_pr_comment("Spacing is off", ["Hiss.", "Meow."])
    assert "## 😼 Criticat Document Review" in body
    assert "Spacing is off" in body
    assert "### 😹 CritiCat Says" in body
    assert "> Hiss.\n> Meow." in body


def test_format_pr_comment_without_jokes(service: PullRequestService) -> None:
    body = service.format_pr_comment("All good", [])
    assert "All good" in body
    assert "CritiCat Says" not in body


def test_token_is_not_exposed_in_repr(service: PullRequestService) -> None:
    assert "ghp_secret" not in repr(service)
