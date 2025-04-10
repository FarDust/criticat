"""
LLM integration module for Criticat.
Handles Vertex AI Gemini model interactions.
"""

import logging
from typing import Tuple

from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI

from criticat.prompts import (
    REVIEW_SYSTEM_PROMPT,
    REVIEW_HUMAN_PROMPT,
    CAT_JOKE_SYSTEM_PROMPT,
    CAT_JOKE_HUMAN_PROMPT,
)


logger = logging.getLogger(__name__)


def initialize_vertex_ai(project_id: str, location: str) -> None:
    """
    Initialize Vertex AI with the given project and location.

    Args:
        project_id: Google Cloud project ID
        location: Google Cloud location
    """
    logger.info(f"Initializing Vertex AI: project={project_id}, location={location}")
    aiplatform.init(project=project_id, location=location)


def get_review_llm(project_id: str, location: str) -> ChatVertexAI:
    """
    Get a LangChain ChatVertexAI instance configured for document review.

    Args:
        project_id: Google Cloud project ID
        location: Google Cloud location

    Returns:
        ChatVertexAI instance
    """
    logger.info("Creating ChatVertexAI instance for document review")
    return ChatVertexAI(
        model_name="gemini-1.5-flash",
        project=project_id,
        location=location,
        max_output_tokens=2048,
        temperature=0.2,
    )


def create_review_prompt() -> ChatPromptTemplate:
    """
    Create a LangChain ChatPromptTemplate for document review.

    Returns:
        ChatPromptTemplate instance
    """
    messages = [
        ("system", REVIEW_SYSTEM_PROMPT),
        ("human", REVIEW_HUMAN_PROMPT),
    ]
    return ChatPromptTemplate.from_messages(messages)


def create_joke_prompt() -> ChatPromptTemplate:
    """
    Create a LangChain ChatPromptTemplate for generating cat jokes.

    Returns:
        ChatPromptTemplate instance
    """
    messages = [
        ("system", CAT_JOKE_SYSTEM_PROMPT),
        ("human", CAT_JOKE_HUMAN_PROMPT),
    ]
    return ChatPromptTemplate.from_messages(messages)


def analyze_review_feedback(feedback: str) -> Tuple[bool, int]:
    """
    Analyze the review feedback to determine if there are issues.

    Args:
        feedback: The LLM review feedback

    Returns:
        Tuple of (has_issues, issue_count)
    """
    # Simple heuristic: if feedback mentions issues or problems, it has issues
    feedback_lower = feedback.lower()
    has_issues = any(
        word in feedback_lower
        for word in ["issue", "problem", "fix", "correct", "improve"]
    )

    # Count the number of issues mentioned (simplistic approach)
    issue_count = feedback_lower.count("issue") + feedback_lower.count("problem")
    if issue_count == 0 and has_issues:
        issue_count = 1

    logger.info(f"Analysis: has_issues={has_issues}, issue_count={issue_count}")
    return has_issues, issue_count


def generate_cat_joke(llm: ChatVertexAI, issue_count: int) -> str:
    """
    Generate a sarcastic cat joke about formatting issues.

    Args:
        llm: ChatVertexAI instance
        issue_count: Number of issues found

    Returns:
        Generated joke string
    """
    logger.info("Generating cat joke")
    try:
        prompt = create_joke_prompt()
        response = llm.invoke(prompt.format(issue_count=issue_count))
        joke = response.content.strip()
        logger.warning(f"Generated cat joke: {joke}")
        return joke
    except Exception as e:
        logger.error(f"Failed to generate cat joke: {e}")
        return "Meow, I tried to think of something witty, but I got distracted by a formatting error."
