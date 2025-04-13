from pydantic import BaseModel, Field


class PRCommentPayload(BaseModel):
    """Payload for the GitHub PR comment."""

    repository: str = Field(description="GitHub repository in format owner/repo")
    pr_number: int = Field(description="Pull request number to comment on")
    body: str = Field(description="Comment body")
