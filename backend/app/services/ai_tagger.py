"""AI Tagger — sends model metadata to Ollama and parses structured tags.

Ollama is exposed via Cloudflare Tunnel on Mac Mini M4 as an
OpenAI-compatible API: POST {OLLAMA_BASE_URL}/v1/chat/completions

The response is forced into JSON format via Ollama's `format: "json"` parameter.
If parsing fails for any reason, a safe fallback AITagResult is returned.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import List

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a 3D printing expert. Analyze the given 3D model metadata and respond "
    "with ONLY a JSON object (no markdown, no explanation) with this exact structure:\n"
    "{\n"
    '  "predicted_name": "Short descriptive name for the model",\n'
    '  "category": "One of: Figurine, Mechanical, Functional, Architecture, Jewelry, '
    'Educational, Vehicle, Animal, Weapon, Other",\n'
    '  "print_type": "One of: FDM, Resin, Unknown",\n'
    '  "keywords": ["keyword1", "keyword2", "keyword3"]\n'
    "}"
)

USER_PROMPT_TEMPLATE = (
    "Analyze this 3D model:\n"
    "- Filename: {filename}\n"
    "- Face count: {face_count:,}\n"
    "- Bounding box: {bbox_x:.1f}mm × {bbox_y:.1f}mm × {bbox_z:.1f}mm\n\n"
    "Respond with the JSON object only."
)


@dataclass
class AITagResult:
    """Structured result from the Ollama AI tagger."""

    predicted_name: str = "Unknown"
    category: str = "Other"
    print_type: str = "Unknown"
    keywords: List[str] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)


async def tag_model(
    filename: str,
    face_count: int,
    bbox: tuple[float, float, float],
) -> AITagResult:
    """Call Ollama API and parse structured tags for a 3D model.

    Returns a safe fallback AITagResult on any error — never raises.

    Args:
        filename: Original filename of the model (e.g. "dragon.stl").
        face_count: Number of faces in the mesh (used as complexity hint).
        bbox: (x_mm, y_mm, z_mm) bounding box dimensions in millimetres.

    Returns:
        AITagResult with parsed fields, or a default fallback on error.
    """
    settings = get_settings()
    bbox_x, bbox_y, bbox_z = bbox

    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename,
        face_count=face_count,
        bbox_x=bbox_x,
        bbox_y=bbox_y,
        bbox_z=bbox_z,
    )

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
    }

    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_content: str = data["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning(f"Ollama returned non-JSON content: {raw_content!r}")
            return AITagResult(raw_response=data)

        return AITagResult(
            predicted_name=parsed.get("predicted_name", "Unknown"),
            category=parsed.get("category", "Other"),
            print_type=parsed.get("print_type", "Unknown"),
            keywords=parsed.get("keywords", []),
            raw_response=data,
        )

    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error for {filename!r}: {e}")
        return AITagResult()
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama for {filename!r}: {e}", exc_info=True)
        return AITagResult()
