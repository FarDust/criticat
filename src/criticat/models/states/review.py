from pydantic import BaseModel, Field

from criticat.models.formatting import FormatReview


class ReviewState(BaseModel):
    """State for the review process."""

    document_images: list[str] = Field(
        default_factory=list, description="List of base64-encoded images of the PDF"
    )
    review_feedback: dict[str, FormatReview] = Field(
        default_factory=dict, description="LLM feedback on the document"
    )
    jokes: list[str] = Field(
        default_factory=list, description="List of cat jokes to inject"
    )


