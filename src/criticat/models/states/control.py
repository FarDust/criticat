from typing import Literal
from pydantic import BaseModel, Field

from criticat.models.config.app import ReviewConfig
from criticat.models.config.git import GitConfig
from criticat.models.states.review import ReviewState

class ControllableConfig(BaseModel):
    git_provider: GitConfig | None = Field(default=None, description="Git provider configuration")
    llm_provider: Literal[
        "vertex_ai",
    ] = Field(description="LLM provider configuration", default="vertex_ai")


class ControlState(BaseModel):
    """
    State to store langgraph interface and work remotely
    with runtime configuration
    """

    review: ReviewState = Field(description="Review state") 
    providers_config: ControllableConfig = Field(description="Controllable configuration by the orchestrator")
    app_config: ReviewConfig = Field(description="Review configuration")
