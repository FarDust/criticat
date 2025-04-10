"""
Pydantic models for the Context Model Protocol (CMP).
These models are used for configuration and state management throughout the application.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class JokeMode(str, Enum):
    """Enum for the different joke modes."""

    NONE = "none"
    DEFAULT = "default"
    CHAOTIC = "chaotic"


class CriticatConfig(BaseModel):
    """Configuration for the Criticat application."""

    pdf_path: str = Field(description="Path to the PDF file to review")
    project_id: str = Field(description="Google Cloud project ID for Vertex AI")
    location: str = Field(
        default="us-central1", description="Google Cloud location for Vertex AI"
    )
    github_token: str = Field(description="GitHub token for API access")
    repository: str = Field(description="GitHub repository in format owner/repo")
    pr_number: int = Field(description="Pull request number to comment on")
    joke_mode: JokeMode = Field(
        default=JokeMode.DEFAULT, description="Mode for injecting cat jokes"
    )


class ReviewState(BaseModel):
    """State for the review process."""

    document_image: Optional[str] = Field(
        default=None, description="Base64-encoded image of the PDF"
    )
    review_feedback: Optional[str] = Field(
        default=None, description="LLM feedback on the document"
    )
    has_issues: bool = Field(
        default=False, description="Whether issues were found in the document"
    )
    issue_count: int = Field(
        default=0, description="Number of issues found in the document"
    )
    jokes: List[str] = Field(
        default_factory=list, description="List of cat jokes to inject"
    )


class FlowState(BaseModel):
    """Combined state for the LangGraph flow."""

    config: CriticatConfig
    state: ReviewState = Field(default_factory=ReviewState)


class PRCommentPayload(BaseModel):
    """Payload for the GitHub PR comment."""

    repository: str
    pr_number: int
    body: str
    github_token: str
