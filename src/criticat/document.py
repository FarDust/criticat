"""
Document extraction module for Criticat.
Handles PDF to image conversion and encoding.
"""

import base64
import io
import logging
from typing import List

from pdf2image import convert_from_path
from PIL import Image


logger = logging.getLogger(__name__)


def convert_pdf_to_images(
    pdf_path: str
) -> List[Image.Image]:
    """
    Convert a PDF file to a list of PIL Image objects.

    Args:
        pdf_path: Path to the PDF file
        first_page_only: Whether to convert only the first page

    Returns:
        List of PIL Image objects
    """
    logger.info(f"Converting PDF to images: {pdf_path}")
    try:
        images = convert_from_path(pdf_path, fmt="jpeg")
        if images:
            return images
        return images
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        raise


def encode_image_to_base64(image: Image.Image) -> str:
    """
    Encode a PIL Image to base64 string.

    Args:
        image: PIL Image object

    Returns:
        Base64-encoded string
    """
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_document_image(pdf_path: str) -> str:
    """
    Extract the first page of a PDF as a base64-encoded image.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Base64-encoded image string
    """
    logger.info(f"Extracting document image from PDF: {pdf_path}")
    images = convert_pdf_to_images(pdf_path)
    if not images:
        logger.error("No images extracted from PDF")
        raise ValueError("No images extracted from PDF")

    return encode_image_to_base64(images[0])
