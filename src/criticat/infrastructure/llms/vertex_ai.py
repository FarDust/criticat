"""
LLM integration module for Criticat.
Handles Vertex AI Gemini model interactions.
"""

from functools import partial
from json import dumps
import logging
from operator import itemgetter
from typing import Any, TypedDict

from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSerializable, RunnableLambda
from langchain_core.messages import SystemMessage

from criticat.models.formatting import FormatReview
from criticat.infrastructure.llms.prompts import (
    REVIEW_SYSTEM_PROMPT,
    REVIEW_HUMAN_PROMPT,
    CAT_JOKE_SYSTEM_PROMPT,
    CAT_JOKE_HUMAN_PROMPT,
)


logger = logging.getLogger(__name__)


class ReviewFeedbackInput(TypedDict):
    """
    Input type for review feedback.
    """

    document_images: list[str]


def initialize_vertex_ai(project_id: str, location: str) -> None:
    """
    Initialize Vertex AI with the given project and location.

    Args:
        project_id: Google Cloud project ID
        location: Google Cloud location
    """
    logger.info(f"Initializing Vertex AI: project={project_id}, location={location}")
    aiplatform.init(project=project_id, location=location)


def get_vertex_llm(project_id: str, location: str) -> ChatVertexAI:
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
        model_name="gemini-1.5-flash-002",
        project=project_id,
        location=location,
        temperature=0.35,
    )


def create_review_prompt(document_images: list[str], schema: dict[str, Any]) -> ChatPromptTemplate:
    """
    Create a LangChain ChatPromptTemplate for document review.

    Returns:
        ChatPromptTemplate instance
    """

    logger.info("Creating review prompt")
    logger.info(f"Document images: {len(document_images)} images")

    images_user_message = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{document_image}",
            },
        }
        for document_image in document_images
    ]
    

    messages = [
        SystemMessage(content=REVIEW_SYSTEM_PROMPT),
        (
            "user",
            [
                {
                    "type": "text",
                    "text": REVIEW_HUMAN_PROMPT.format(
                        schema=dumps(schema, indent=2)
                        .replace("{", "{{")
                        .replace("}", "}}")
                    ),
                },
            ] + images_user_message,
        ),
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
        ("user", CAT_JOKE_HUMAN_PROMPT),
    ]
    return ChatPromptTemplate.from_messages(messages)


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
        response: str = (llm | StrOutputParser()).invoke(
            prompt.format(issue_count=issue_count)
        )
        joke = response.strip()
        logger.warning(f"Generated cat joke: {joke}")
        return joke
    except Exception as e:
        logger.error(f"Failed to generate cat joke: {e}")
        return "Meow, I tried to think of something witty, but I got distracted by a formatting error."


def review_feedback_chain(
    project_id: str,
    location: str,
) -> RunnableSerializable[ReviewFeedbackInput, FormatReview]:
    # Initialize Vertex AI
    initialize_vertex_ai(
        project_id=project_id,
        location=location,
    )

    # Get LLM and prompt
    llm = get_vertex_llm(
        project_id=project_id,
        location=location,
    ).with_structured_output(FormatReview)

    prompt_generation = partial(create_review_prompt, schema=FormatReview.model_json_schema())

    # Invoke LLM
    logger.info("Invoking LLM for document review")
    review_feedback_chain: RunnableSerializable[ReviewFeedbackInput, FormatReview] = (
        RunnableLambda(lambda inputs: prompt_generation(
            document_images=inputs["document_images"],
        )) | llm
    )

    return review_feedback_chain

def joke_chain(
    project_id: str,
    location: str
) -> RunnableSerializable[dict[str, Any], str]:
    
    # Initialize Vertex AI
    initialize_vertex_ai(
        project_id=project_id,
        location=location,
    )

    llm = get_vertex_llm(
        project_id=project_id,
        location=location,
    )

    prompt = create_joke_prompt()

    joke_chain: RunnableSerializable[dict[str, Any], str] = {
        "review_feedback": itemgetter("review_feedback"),
    } | prompt | llm | StrOutputParser()
    

    return joke_chain


