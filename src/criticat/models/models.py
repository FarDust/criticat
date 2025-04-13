from pydantic import BaseModel, Field


class VertexAIConfig(BaseModel):
    llm_provider: str = Field(default="vertex_ai")
    """Configuration for Vertex AI LLM provider."""

    project_id: str = Field(description="Google Cloud project ID for Vertex AI")
    location: str = Field(
        default="us-central1", description="Google Cloud location for Vertex AI"
    )
