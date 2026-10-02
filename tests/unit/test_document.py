"""Tests for PDF rendering and encoding."""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from criticat import document
from criticat.document import (
    convert_pdf_to_images,
    encode_image_to_base64,
    extract_document_image,
)
from tests.conftest import requires_poppler


def test_encode_image_to_base64_produces_jpeg() -> None:
    encoded = encode_image_to_base64(Image.new("RGB", (10, 10), "red"))
    raw = base64.b64decode(encoded)
    assert raw[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(raw)).size == (10, 10)


def test_extract_document_image_rejects_empty_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document, "convert_from_path", lambda *a, **k: [])
    with pytest.raises(ValueError, match="No images extracted"):
        extract_document_image("doc.pdf")


def test_convert_pdf_to_images_propagates_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> list[Image.Image]:
        raise RuntimeError("poppler crashed")

    monkeypatch.setattr(document, "convert_from_path", boom)
    with pytest.raises(RuntimeError, match="poppler crashed"):
        convert_pdf_to_images("doc.pdf")


@requires_poppler
def test_convert_real_pdf(sample_pdf: Path) -> None:
    images = convert_pdf_to_images(str(sample_pdf))
    assert len(images) == 2
    assert all(image.width > 0 and image.height > 0 for image in images)


@requires_poppler
def test_extract_real_pdf(sample_pdf: Path) -> None:
    encoded = extract_document_image(str(sample_pdf))
    assert len(encoded) == 2
    assert all(base64.b64decode(page)[:2] == b"\xff\xd8" for page in encoded)


@requires_poppler
def test_convert_invalid_pdf_raises(fake_pdf: Path) -> None:
    with pytest.raises(Exception):  # noqa: B017
        convert_pdf_to_images(str(fake_pdf))
