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
    "Bạn là một chuyên gia in 3D. Hãy phân tích các thông số và NỘI DUNG TIN NHẮN (nếu có) của model 3D này.\n"
    "Quy tắc phân loại:\n"
    "- Nếu face count > 500,000, khả năng cao là in Resin.\n"
    "- Nếu có các từ khoá cơ khí, bánh răng, lắp ráp... thì thường là FDM.\n"
    "Bạn PHẢI trả về duy nhất một object JSON (không markdown, không giải thích) với cấu trúc:\n"
    "{\n"
    '  "predicted_name": "Tên tiếng Việt rõ ràng, ngắn gọn của model (xoá các đuôi file .stl, .zip, v.v...)",\n'
    '  "category": "Một trong: Figurine, Mechanical, Functional, Architecture, Jewelry, Educational, Vehicle, Animal, Weapon, Other",\n'
    '  "print_type": "Một trong: FDM, Resin, Unknown",\n'
    '  "keywords": ["từ khoá tiếng việt 1", "từ khoá tiếng việt 2"]\n'
    "}"
)

USER_PROMPT_TEMPLATE = (
    "Phân tích model 3D sau:\n"
    "- Filename: {filename}\n"
    "- Face count: {face_count:,}\n"
    "- Bounding box: {bbox_x:.1f}mm × {bbox_y:.1f}mm × {bbox_z:.1f}mm\n"
    "- Nội dung tin nhắn gốc: {message_text}\n\n"
    "Chỉ trả về JSON object."
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
    message_text: str = "",
) -> AITagResult:
    """Call Ollama API and parse structured tags for a 3D model.

    Returns a safe fallback AITagResult on any error — never raises.

    Args:
        filename: Original filename of the model (e.g. "dragon.stl").
        face_count: Number of faces in the mesh (used as complexity hint).
        bbox: (x_mm, y_mm, z_mm) bounding box dimensions in millimetres.
        message_text: Original Telegram message text for extra context.

    Returns:
        AITagResult with parsed fields, or a default fallback on error.
    """
    env_settings = get_settings()
    from app.services.settings import SettingsService
    
    ollama_base_url = await SettingsService.get_setting("OLLAMA_BASE_URL", env_settings.OLLAMA_BASE_URL)
    ollama_model = await SettingsService.get_setting("OLLAMA_MODEL", env_settings.OLLAMA_MODEL)
    
    bbox_x, bbox_y, bbox_z = bbox

    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename,
        face_count=face_count,
        bbox_x=bbox_x,
        bbox_y=bbox_y,
        bbox_z=bbox_z,
        message_text=message_text,
    )

    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
    }

    base_url_clean = ollama_base_url.rstrip('/')
    if base_url_clean.endswith('/v1'):
        base_url_clean = base_url_clean[:-3]
        
    url = f"{base_url_clean}/v1/chat/completions"

    try:
        logger.info(f"[{filename}] Sending context to LLM: {json.dumps(payload, ensure_ascii=False)}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_content: str = data["choices"][0]["message"]["content"]
        
        full_debug_info = {
            "request_payload": payload,
            "response_data": data
        }

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning(f"Ollama returned non-JSON content: {raw_content!r}")
            return AITagResult(raw_response=full_debug_info)

        return AITagResult(
            predicted_name=parsed.get("predicted_name", "Unknown"),
            category=parsed.get("category", "Other"),
            print_type=parsed.get("print_type", "Unknown"),
            keywords=parsed.get("keywords", []),
            raw_response=full_debug_info,
        )

    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error for {filename!r}: {e}")
        return AITagResult()
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama for {filename!r}: {e}", exc_info=True)
        return AITagResult()
