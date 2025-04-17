"""
Context Model Protocol (CMP) server implementation for Criticat.
Uses the MCP framework to provide tools and resources.
"""

import logging
import sys # Import sys for stdout handler
from typing import Optional

# Configure logging early
logging.basicConfig(
    level=logging.DEBUG, # Ensure logging level is DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)], # Ensure output goes to stdout
)
logger = logging.getLogger(__name__)
logger.info("Logging configured.") # Add an early log message

from mcp.server.fastmcp import FastMCP

from criticat.models.config.app import JokeMode, ReviewConfig
from criticat.models.config.environment import get_gcp_project_id, get_gcp_location
from criticat.models.models import VertexAIConfig
from criticat.models.states.review import ReviewState
from criticat.use_cases.review import ReviewPDF


# Create the MCP server
mcp = FastMCP(name="Criticat")


# Register the review tool
@mcp.tool()
def review(
    pdf_path: str, # Ensure original signature
    project_id: Optional[str] = None, # Ensure original signature
    location: Optional[str] = None, # Ensure original signature
    joke_mode: str = "default", # Ensure original signature
) -> ReviewState:
    """
    Review a PDF document and generates a report.
    
    Parameters
    ----------
    pdf_path : str
        Path to the PDF file to review.
    project_id : Optional[str], optional
        Google Cloud project ID. Defaults to CRITICAT_GCP_PROJECT_ID 
        environment variable if None.
    location : Optional[str], optional
        Google Cloud location. Defaults to CRITICAT_GCP_LOCATION 
        environment variable or 'us-central1' if None.
    joke_mode : str, optional
        Mode for injecting cat jokes ('none', 'default', 'chaotic'). 
        Defaults to "default".

    Returns
    -------
    ReviewState
        An object containing the review results (feedback and jokes).
        
    Raises
    ------
    ValueError
        If no GCP project ID is provided or found in the environment.
    ValueError
        If an invalid value is provided for joke_mode.
    """
    logger.info(f"MCP review tool called for PDF: {pdf_path}") # Keep INFO level for key events
    logger.debug(f"Received arguments: project_id={project_id}, location={location}, joke_mode={joke_mode}") # DEBUG for details

    try: # Add try/except within the tool function
        final_project_id = project_id or get_gcp_project_id()
        if not final_project_id:
            logger.error("Missing project ID for review tool.")
            raise ValueError(
                "No GCP project ID provided. Either set CRITICAT_GCP_PROJECT_ID environment variable "
                "or provide project_id parameter."
            )
        logger.debug(f"Using project_id: {final_project_id}")

        final_location = location or get_gcp_location()
        logger.debug(f"Using location: {final_location}")

        try:
            joke_mode_enum = JokeMode(joke_mode)
            logger.debug(f"Using joke_mode: {joke_mode_enum}")
        except ValueError as e:
            logger.error(f"Invalid joke_mode value: {joke_mode}. Error: {e}")
            raise ValueError(f"Invalid joke_mode: {joke_mode}") from e


        config = ReviewConfig(
            pdf_path=pdf_path,
            joke_mode=joke_mode_enum,
        )
        logger.debug("ReviewConfig created.")

        vertex_config = VertexAIConfig(
                project_id=final_project_id,
                location=final_location,
            )
        logger.debug("VertexAIConfig created.")

        review_use_case = ReviewPDF(provider_configs=[vertex_config])
        logger.debug("ReviewPDF use case instantiated.")

        logger.info("Starting review_use_case._run()...")
        final_state = review_use_case._run(
            config=config.model_dump(),
        )
        logger.info("review_use_case._run() completed.")
        logger.debug(f"Final state keys: {final_state.keys() if isinstance(final_state, dict) else 'Not a dict'}")


        if "review" not in final_state:
             logger.error("Key 'review' not found in final_state returned by use case.")
             # Depending on MCP, you might need to raise an exception or return an error state
             raise KeyError("Internal error: 'review' state missing from use case result.")

        review_result = final_state["review"]
        logger.info("Review completed successfully, returning result.")
        logger.debug(f"Result type: {type(review_result)}")
        return review_result

    except Exception as e:
        logger.exception("An error occurred within the review tool function.")
        # Re-raise the exception so MCP framework can potentially handle it and send an error response
        raise

def main():
    """Starts the MCP server."""
    logger.info("Starting MCP server (stdio transport)...")
    try:
        # Start the server using the default 'stdio' transport
        mcp.run(transport="stdio") # Ensure stdio transport
    except Exception as e:
        logger.exception(f"MCP server failed: {e}") # Log any exception during run
    finally:
        logger.info("MCP server finished or was interrupted.")

if __name__ == "__main__":
    main() # Call the main function when run directly

