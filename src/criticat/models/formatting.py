from typing import Literal

from pydantic import BaseModel, Field

FormatCategoryName = Literal[
    # "word_spacing",
    # "character_spacing",
    # "section_spacing",
    # "paragraph_spacing",
    "text_alignment",
    "font_quality",
    "rendering_quality",
    "bullet_formatting",
    "list_formatting",
    "visual_alignment",
    "image_occlusion",
    "text_occlusion",
    "table_formatting",
    "header_and_footer_alignment",
    "margin_and_padding_issues",
    "color_contrast",
    "line_spacing",
    "page_numbering",
    "footnote_formatting",
    "caption_alignment",
    "hyperlink_formatting",
]


class IssueBoundingBox(BaseModel):
    example: str = Field(
        default="",
        description=(
            "Example or snippet from the document where the issue occurs. "
            "In an OCR setting, this could include the text that was misinterpreted, "
            "hints about nearby LaTeX commands, or whether the straight text is legible. "
            "This provides context to help identify and resolve the issue."
        ),
    )

    bounding_box: list[int] = Field(
        ...,
        description=(
            "Bounding box coordinates of the issue in the document. "
            "This should be a list of four floats representing the coordinates of the "
            "bounding box (x1, y1, x2, y2) in the document."
        ),
    )


class FormatIssue(BaseModel):
    description: str = Field(
        ...,
        description=(
            "A concise description of the formatting issue, summarizing its nature and impact. "
            "This should include key details to quickly understand the issue, such as its status level."
        ),
    )
    explanation: str = Field(
        ...,
        description=(
            "Explanation of the issue, where it occurs, its status, and confidence level. "
            "This should provide a detailed context for understanding the issue, including "
            "why it is categorized under a specific status and the confidence level associated with it."
        ),
    )
    error_location: IssueBoundingBox = Field(
        ...,
        description=(
            "The location of the error in the document. This field is used to "
            "specify the bounding box or area where the issue occurs."
        ),
    )
    cause: str = Field(
        ...,
        description=("Likely cause of the issue (e.g., LaTeX misconfiguration). "),
    )
    status: Literal["critical", "error", "warning", "info"] = Field(
        ...,
        description=(
            "Status of the issue.\n"
            "Critical: An issue that completely breaks the document, like occlusion "
            "or cut-off text.\n"
            "Error: An issue that can prevent reading something"
            "between paragraphs that can be easily fixed with adjustments to the "
            "LaTeX code.\n"
            "Warning: A minor fix that could be great for readability.\n"
            "Info: Good to know."
        ),
    )
    confidence: int = Field(
        ...,
        description=(
            "Confidence level from 1 to 5, representing the degree of certainty about the accuracy and relevance of the identified issue:\n"
            "1: Very low confidence - The issue is highly uncertain, and it might not be accurate or relevant. It is recommended to thoroughly verify before taking any action.\n"
            "2: Low confidence - The issue is likely relevant but still requires further verification. There is a significant chance of false positives.\n"
            "3: Medium confidence - The issue is reasonably accurate and likely relevant. It is a balanced level of confidence, suitable for most cases where some uncertainty is acceptable.\n"
            "4: High confidence - The issue is accurate and relevant in most cases. It is reliable and can generally be trusted without extensive verification.\n"
            "5: Very high confidence - The issue is almost certainly accurate and highly relevant. It is highly reliable and can be acted upon with minimal or no verification."
        ),
        ge=1,
        le=5,
    )


class FormatCategoryItem(BaseModel):
    name: FormatCategoryName = Field(
        ..., description="The name of the formatting issue category."
    )
    issues: list[FormatIssue] = Field(
        ..., description="List of formatting issues in this category."
    )


class FormatReview(BaseModel):
    explanation: str = Field(..., description="Explanation of the review.")
    categories: list[FormatCategoryItem] = Field(
        ..., description="All detected categories and their issues."
    )

    def has_issues(self) -> bool:
        for category in self.categories:
            if any(issue.status in ["critical", "error"] for issue in category.issues):
                return True
        return False

    def issue_count(self) -> int:
        count = 0
        for category in self.categories:
            count += len(category.issues)
        return count
