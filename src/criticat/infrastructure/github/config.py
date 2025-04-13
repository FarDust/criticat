from pydantic import BaseModel, Field, SecretStr


class GithubConfig(BaseModel):
    """Configuration for the Criticat application."""

    github_token: SecretStr = Field(description="GitHub token for API access")
    repository: str = Field(description="GitHub repository in format owner/repo")
