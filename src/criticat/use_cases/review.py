"""
LangGraph flow implementation for Criticat.
Defines the document review workflow as a graph of nodes.
"""

import logging
from pathlib import Path
import random
from typing import Dict, Any, TypedDict

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

from criticat.document import extract_document_image
from criticat.infrastructure.llms.vertex_ai import (
    joke_chain,
    review_feedback_chain,
)

# from criticat.infrastructure.github.pull_request import comment_on_pr, format_pr_comment
from criticat.models.config.app import JokeMode
from criticat.models.formatting import FormatReview
from criticat.models.models import VertexAIConfig
from criticat.models.states.control import ControlState
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableSerializable


logger = logging.getLogger(__name__)


class ReviewProvider(TypedDict):
    review: RunnableSerializable
    joke: RunnableSerializable


class ReviewPDF:
    def __init__(self, provider_configs: list[BaseModel]):
        self._providers_config: dict[str, VertexAIConfig | BaseModel] = {}
        self._providers: dict[str, ReviewProvider] = {}

        for provider_config in provider_configs:
            if hasattr(provider_config, "llm_provider"):
                self._providers[provider_config.llm_provider] = {}
                if isinstance(provider_config, VertexAIConfig):
                    self._providers_config[provider_config.llm_provider] = (
                        provider_config
                    )
                    self._providers[provider_config.llm_provider]["review"] = (
                        review_feedback_chain(
                            project_id=provider_config.project_id,
                            location=provider_config.location,
                        )
                    )
                    self._providers[provider_config.llm_provider]["joke"] = joke_chain(
                        project_id=provider_config.project_id,
                        location=provider_config.location,
                    )
                elif hasattr(provider_config, "llm_provider") and isinstance(
                    provider_config.llm_provider, str
                ):
                    self._providers_config[provider_config.llm_provider] = (
                        provider_config
                    )
                    if hasattr(provider_config, "review") and callable(
                        provider_config.review
                    ):
                        self._providers[provider_config.llm_provider]["review"] = (
                            provider_config.review(**provider_config.model_dump())
                        )
                    if hasattr(provider_config, "joke") and callable(
                        provider_config.joke
                    ):
                        self._providers[provider_config.llm_provider]["joke"] = (
                            provider_config.joke(**provider_config.model_dump())
                        )

    def extract_text_node(self, state: ControlState) -> ControlState:
        """
        Extract text from PDF document.

        Args:
            state: LangGraph state dictionary

        Returns:
            Updated state dictionary
        """
        logger.info("Running extract_text_node")
        flow_state = ControlState.model_validate(state)

        # Convert PDF to image
        document_images = extract_document_image(flow_state.app_config.pdf_path)
        flow_state.review.document_images = document_images

        logger.info("Successfully extracted document image from PDF")
        return flow_state

    def review_llm_node(self, state: ControlState) -> ControlState:
        """
        Review document using LLM.

        Args:
            state: LangGraph state dictionary

        Returns:
            Updated state dictionary
        """
        logger.info("Running review_llm_node")
        flow_state = ControlState.model_validate(state)

        assert (
            flow_state.review.document_images is not None
        ), "Document images are required"

        for provider_name, provider in self._providers.items():
            review_feedback: FormatReview = provider["review"].invoke(
                input={
                    "document_images": flow_state.review.document_images,
                }
            )

            flow_state.review.review_feedback[provider_name] = review_feedback

        # Handle jokes based on joke mode
        joke_mode = flow_state.app_config.joke_mode
        for provider_name, provider in self._providers.items():
            if joke_mode == JokeMode.CHAOTIC:
                # In chaotic mode, always add 1-3 jokes
                joke_count = random.randint(1, 3)
                logger.warning(f"Chaotic mode activated: adding {joke_count} jokes")
                for _ in range(joke_count):
                    joke = provider["joke"].invoke(
                        input={
                            "review_feedback": flow_state.review.review_feedback[
                                provider_name
                            ]
                        }
                    )
                    flow_state.review.jokes.append(joke)
            elif (
                joke_mode == JokeMode.DEFAULT
                and flow_state.review.review_feedback[provider_name].has_issues()
            ):
                # In default mode, add 1 joke if issues were found
                logger.info("Default mode: adding 1 joke for found issues")
                joke = provider["joke"].invoke(
                    input={
                        "review_feedback": flow_state.review.review_feedback[
                            provider_name
                        ]
                    }
                )
                flow_state.review.jokes.append(joke)
            elif joke_mode == JokeMode.NONE:
                logger.info("Joke mode is set to NONE, no jokes will be added")

        reports_path = Path("./reports").absolute().resolve()
        reports_path.mkdir(exist_ok=True)

        with Path(reports_path / "criticat_feedback.json").open("w") as f:
            f.write(
                flow_state.review.model_dump_json(indent=2, exclude={"document_images"})
            )

        return flow_state

    def comment_pr_node(self, state: ControlState) -> ControlState:
        """
        Comment on PR if issues were found.

        Args:
            state: LangGraph state dictionary

        Returns:
            Updated state dictionary
        """
        logger.info("Running comment_pr_node")
        flow_state = ControlState.model_validate(state)

        if False:
            logger.info("Issues found, commenting on PR")
            # Format PR comment
            # comment_body = format_pr_comment(
            #     review_feedback=flow_state.state.review_feedback
            #     if flow_state.state.review_feedback
            #     else "",
            #     jokes=flow_state.state.jokes,
            # )

            # # Create payload
            # payload = PRCommentPayload(
            #     repository=flow_state.config.repository,
            #     pr_number=flow_state.config.pr_number,
            #     body=comment_body,
            #     github_token=flow_state.config.github_token,
            # )

            # # Comment on PR
            # comment_on_pr(payload)
        else:
            logger.info("No issues found, skipping PR comment")

        return flow_state

    def should_comment_on_pr(self, state: ControlState) -> str:
        """
        Determine if we should comment on the PR.

        Args:
            state: LangGraph state dictionary

        Returns:
            Next node name
        """
        flow_state = ControlState.model_validate(state)
        if not flow_state.providers_config.git_provider:
            return END
        if False:
            return "comment_pr"
        return END

    def create_review_graph(self) -> CompiledStateGraph:
        """
        Create a LangGraph for document review.

        Returns:
            CompiledStateGraph instance
        """
        # Create graph builder
        builder = StateGraph(ControlState)

        # Add nodes
        builder.add_node("extract_text", self.extract_text_node)
        builder.add_node("review_llm", self.review_llm_node)
        builder.add_node("comment_pr", self.comment_pr_node)

        # Add edges
        builder.add_edge(START, "extract_text")
        builder.add_edge("extract_text", "review_llm")
        builder.add_conditional_edges(
            "review_llm",
            self.should_comment_on_pr,
            {"comment_pr": "comment_pr", END: END},
        )
        builder.add_edge("comment_pr", END)

        # Compile graph
        return builder.compile()

    def _run(self, config: Dict[str, Any]) -> ControlState:
        """
        Run the document review graph with the given configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Final state dictionary
        """
        # Create initial state
        initial_state = {
            "app_config": config,
            "providers_config": {"git_provider": config.get("git_provider", None)},
            "review": {"document_images": [], "review_feedback": {}, "jokes": []},
        }

        # Create graph
        graph = self.create_review_graph()

        # Run graph
        logger.info("Starting document review graph")
        final_state = graph.invoke(ControlState(**initial_state))
        logger.info("Document review graph completed")

        return final_state
