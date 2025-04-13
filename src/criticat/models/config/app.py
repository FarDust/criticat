from enum import Enum
from pydantic import BaseModel, Field


class JokeMode(str, Enum):
    """Enum for the different joke modes."""

    NONE = "none"
    DEFAULT = "default"
    CHAOTIC = "chaotic"


class ReviewConfig(BaseModel):
    pdf_path: str = Field(description="Path to the PDF file to review")
    joke_mode: JokeMode = Field(
        default=JokeMode.DEFAULT, description="Mode for injecting cat jokes"
    )