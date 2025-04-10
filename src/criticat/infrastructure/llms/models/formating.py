from pydantic import BaseModel, Field
from typing import List
from typing import Literal

FormatCategoryName = Literal[
    "word_and_character_spacing",
    "section_and_paragraph_spacing",
    "text_alignment",
    "font_and_rendering_quality",
    "bullet_and_list_formatting",
    "visual_element_alignment",
    "occlusion"
]


class FormatIssue(BaseModel):
    description: str = Field(..., description="Brief description of the formatting issue.")
    explanation: str = Field(..., description="Explanation of the issue.")
    example: str = Field("", description="Example or snippet from the document.")  # No Optional
    cause: str = Field("", description="Likely cause of the issue (e.g., LaTeX misconfig).")
    status: Literal["warning", "error", "info"] = Field(..., description="Status of the issue.\n Error: An issue that can prevent to read something, like occlusion between paragraphs that that can be easily fixed with adjustments to the LaTeX code\n Warning: a minor fix that could be great for readability, like minor disalignment of visual components\n Info: good to now")
    confidence: int = Field(..., description="Confidence level from 1 to 5.", ge=1, le=5)



class FormatCategoryItem(BaseModel):
    name: FormatCategoryName = Field(..., description="The name of the formatting issue category.")
    issues: List[FormatIssue] = Field(..., description="List of formatting issues in this category.")


class FormatReview(BaseModel):
    explanation: str = Field(..., description="Explanation of the review.")
    categories: List[FormatCategoryItem] = Field(..., description="All detected categories and their issues.")