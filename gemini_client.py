"""Wrapper around Google's Gemini 2.5 Flash Image ("Nano Banana") API.

Returns raw image bytes (PNG) so they can be sent back to Telegram.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Iterable

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

# "Nano Banana" = Gemini 2.5 Flash Image
MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image")


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _extract_images(response) -> list[bytes]:
    """Pull every inline image out of a Gemini response as PNG bytes."""
    images: list[bytes] = []
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                images.append(inline.data)
    return images


def generate_images(prompt: str, n: int = 1) -> list[bytes]:
    """Generate `n` images from a text prompt."""
    client = _client()
    results: list[bytes] = []

    # Gemini image model returns one image per call — loop for multiple variants.
    for i in range(max(1, n)):
        logger.info("Generating image %d/%d for prompt: %s", i + 1, n, prompt[:80])
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[prompt],
        )
        results.extend(_extract_images(response))

    if not results:
        raise RuntimeError(
            "Gemini returned no images. Prompt may have been blocked by safety filters."
        )
    return results


def edit_image(image_bytes: bytes, prompt: str) -> bytes:
    """Edit/transform an uploaded image using a text prompt."""
    client = _client()

    # Let PIL normalize whatever Telegram sent us (JPEG/WEBP/etc.) to PNG.
    pil_image = Image.open(io.BytesIO(image_bytes))

    logger.info("Editing image with prompt: %s", prompt[:80])
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[prompt, pil_image],
    )

    images = _extract_images(response)
    if not images:
        raise RuntimeError(
            "Gemini returned no image. The edit may have been blocked by safety filters."
        )
    return images[0]
