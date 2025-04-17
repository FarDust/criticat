"""
Environment configuration module for Criticat.

This module uses Pydantic's Settings management to load configuration
from environment variables with proper type conversion and validation.
It also respects standard Google Cloud SDK environment variables.
"""

import os
from typing import Optional
import logging
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class CriticatSettings(BaseSettings):
    """
    Application settings loaded from environment variables with CRITICAT_ prefix.
    Also respects standard Google Cloud SDK environment variables as fallbacks.
    """

    # Google Cloud settings - will check standard GCP env vars in get_gcp_project_id
    gcp_project_id: Optional[str] = None
    gcp_location: str = "us-central1"

    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Add more settings as needed

    # Any API keys or tokens should use SecretStr to prevent logging
    openai_api_key: Optional[SecretStr] = None

    model_config = SettingsConfigDict(
        env_prefix="CRITICAT_",
        env_file=".envrc",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra fields that aren't in the model
    )


# Global settings instance
settings = CriticatSettings()


# Convenience functions for common settings with GCP environment variable fallbacks
def get_gcp_project_id() -> Optional[str]:
    """
    Get the GCP project ID from environment.
    Checks CRITICAT_GCP_PROJECT_ID first, then falls back to
    standard GCP environment variables.
    """
    # First check our settings from CRITICAT_GCP_PROJECT_ID
    project_id = settings.gcp_project_id

    # If not found, check standard Google Cloud SDK environment variables
    if not project_id:
        # Check CLOUDSDK_CORE_PROJECT (gcloud default)
        project_id = os.environ.get("CLOUDSDK_CORE_PROJECT")

        # If still not found, check GOOGLE_CLOUD_PROJECT (common in GCP environments)
        if not project_id:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        logger.warning(
            "No GCP project ID found in environment variables. "
            "Set one of: CRITICAT_GCP_PROJECT_ID, CLOUDSDK_CORE_PROJECT, "
            "GOOGLE_CLOUD_PROJECT, or GCLOUD_PROJECT environment variables."
        )

    return project_id


def get_gcp_location() -> str:
    """
    Get the GCP location from environment.
    Checks CRITICAT_GCP_LOCATION first, then falls back to
    CLOUDSDK_COMPUTE_REGION, with a final default of 'us-central1'.
    """
    # First check our settings from CRITICAT_GCP_LOCATION
    location = settings.gcp_location

    # If using default, check for standard GCP region variable
    if location == "us-central1":  # Check if using default value
        cloud_region = os.environ.get("CLOUDSDK_COMPUTE_REGION")
        if cloud_region:
            location = cloud_region

    return location
