"""
LangGraph flow implementation for Criticat.
Defines the document review workflow as a graph of nodes.
"""

import logging
import random
from typing import Dict, Any, TypedDict

from langgraph.graph import StateGraph, START, END

from criticat.document import extract_document_image
from criticat.llm import (
    initialize_vertex_ai,
    get_review_llm,
    create_review_prompt,
    analyze_review_feedback,
    generate_cat_joke,
)
from criticat.github import comment_on_pr, format_pr_comment
from criticat.models import FlowState, JokeMode, PRCommentPayload


logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """State dictionary for the graph."""

    config: Dict[str, Any]
    state: Dict[str, Any]


def extract_text_node(state: GraphState) -> GraphState:
    """
    Extract text from PDF document.

    Args:
        state: LangGraph state dictionary

    Returns:
        Updated state dictionary
    """
    logger.info("Running extract_text_node")
    flow_state = FlowState.model_validate(state)

    # Convert PDF to image
    document_image = extract_document_image(flow_state.config.pdf_path)
    flow_state.state.document_image = document_image

    logger.info("Successfully extracted document image from PDF")
    return flow_state.model_dump()


def review_llm_node(state: GraphState) -> GraphState:
    """
    Review document using LLM.

    Args:
        state: LangGraph state dictionary

    Returns:
        Updated state dictionary
    """
    logger.info("Running review_llm_node")
    flow_state = FlowState.model_validate(state)

    # Initialize Vertex AI
    initialize_vertex_ai(
        project_id=flow_state.config.project_id,
        location=flow_state.config.location,
    )

    # Get LLM and prompt
    llm = get_review_llm(
        project_id=flow_state.config.project_id,
        location=flow_state.config.location,
    )
    prompt = create_review_prompt()

    # Invoke LLM
    logger.info("Invoking LLM for document review")
    document_image = flow_state.state.document_image
    response = llm.invoke(prompt.format(document_image=document_image))
    review_feedback = response.content

    # Update state
    flow_state.state.review_feedback = review_feedback
    has_issues, issue_count = analyze_review_feedback(review_feedback)
    flow_state.state.has_issues = has_issues
    flow_state.state.issue_count = issue_count

    # Handle jokes based on joke mode
    joke_mode = flow_state.config.joke_mode
    if joke_mode == JokeMode.CHAOTIC:
        # In chaotic mode, always add 1-3 jokes
        joke_count = random.randint(1, 3)
        logger.warning(f"Chaotic mode activated: adding {joke_count} jokes")
        for _ in range(joke_count):
            joke = generate_cat_joke(llm, issue_count)
            flow_state.state.jokes.append(joke)
    elif joke_mode == JokeMode.DEFAULT and has_issues:
        # In default mode, add 1 joke if issues were found
        logger.info("Default mode: adding 1 joke for found issues")
        joke = generate_cat_joke(llm, issue_count)
        flow_state.state.jokes.append(joke)
    elif joke_mode == JokeMode.NONE:
        logger.info("Joke mode is set to NONE, no jokes will be added")

    return flow_state.model_dump()


def comment_pr_node(state: GraphState) -> GraphState:
    """
    Comment on PR if issues were found.

    Args:
        state: LangGraph state dictionary

    Returns:
        Updated state dictionary
    """
    logger.info("Running comment_pr_node")
    flow_state = FlowState.model_validate(state)

    if flow_state.state.has_issues:
        logger.info("Issues found, commenting on PR")
        # Format PR comment
        comment_body = format_pr_comment(
            review_feedback=flow_state.state.review_feedback,
            jokes=flow_state.state.jokes,
        )

        # Create payload
        payload = PRCommentPayload(
            repository=flow_state.config.repository,
            pr_number=flow_state.config.pr_number,
            body=comment_body,
            github_token=flow_state.config.github_token,
        )

        # Comment on PR
        comment_on_pr(payload)
    else:
        logger.info("No issues found, skipping PR comment")

    return flow_state.model_dump()


def should_comment_on_pr(state: GraphState) -> str:
    """
    Determine if we should comment on the PR.

    Args:
        state: LangGraph state dictionary

    Returns:
        Next node name
    """
    flow_state = FlowState.model_validate(state)
    if flow_state.state.has_issues:
        return "comment_pr"
    return END


def create_review_graph() -> StateGraph:
    """
    Create a LangGraph for document review.

    Returns:
        StateGraph instance
    """
    # Create graph builder
    builder = StateGraph(GraphState)

    # Add nodes
    builder.add_node("extract_text", extract_text_node)
    builder.add_node("review_llm", review_llm_node)
    builder.add_node("comment_pr", comment_pr_node)

    # Add edges
    builder.add_edge(START, "extract_text")
    builder.add_edge("extract_text", "review_llm")
    builder.add_conditional_edges(
        "review_llm", should_comment_on_pr, {"comment_pr": "comment_pr", END: END}
    )
    builder.add_edge("comment_pr", END)

    # Compile graph
    return builder.compile()


def run_review_graph(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the document review graph with the given configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Final state dictionary
    """
    # Create initial state
    initial_state = {
        "config": config,
        "state": {
            "document_image": None,
            "review_feedback": None,
            "has_issues": False,
            "issue_count": 0,
            "jokes": [],
        },
    }

    # Create graph
    graph = create_review_graph()

    # Run graph
    logger.info("Starting document review graph")
    final_state = graph.invoke(initial_state)
    logger.info("Document review graph completed")

    return final_state
