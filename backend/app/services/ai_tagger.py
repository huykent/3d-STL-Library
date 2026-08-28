"""AI Tagger — sends model metadata to Ollama and parses structured tags & studio.

Ollama is exposed via Cloudflare Tunnel on Mac Mini M4 as an
OpenAI-compatible API: POST {OLLAMA_BASE_URL}/v1/chat/completions
"""
from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

KNOWN_STUDIOS = [
    "Gambody", "Sanix", "Wicked", "Nomad", "Nomad Sculpt", "Torida", "Malix",
    "B3DSERK", "Hex3D", "EastCoast", "Cgtrader", "Cults3D", "Loot Studios",
    "Archvillain", "Titan Forge", "MyMiniFactory", "Fotis Mint", "Star Wars 3D"
]


def detect_known_studio(filename: str, message_text: str = "") -> Optional[str]:
    """Heuristic fallback detector for well-known 3D modeling studios."""
    clean_text = re.sub(r"[^a-zA-Z0-9]", " ", f"{filename} {message_text}").lower()
    for studio in KNOWN_STUDIOS:
        pattern = r"\b" + re.escape(studio.lower()) + r"\b"
        if re.search(pattern, clean_text):
            return studio
    return None


SYSTEM_PROMPT = (
    "Bạn là một chuyên gia in 3D. Hãy phân tích các thông số và NỘI DUNG TIN NHẮN của model 3D này.\n"
    "Quy tắc phân loại:\n"
    "- Nếu face count > 500,000 hoặc có hỗ trợ pre-supported, khả năng cao là in Resin.\n"
    "- Nếu có các từ khoá cơ khí, bánh răng, lắp ráp... thì thường là FDM.\n"
    "- Cố gắng nhận diện tên Studio/Tác giả (Ví dụ: Gambody, Sanix, Wicked, Nomad, Malix...) nếu có trong tên file hoặc mô tả.\n"
    "Bạn PHẢI trả về duy nhất một object JSON (không markdown, không giải thích) với cấu trúc:\n"
    "{\n"
    '  "predicted_name": "Tên rõ ràng, ngắn gọn của model (xoá các đuôi file .stl, .zip, v.v...)",\n'
    '  "studio": "Tên Studio / Tác giả nếu phát hiện, hoặc null",\n'
    '  "category": "Một trong: Figurine, Mechanical, Functional, Architecture, Jewelry, Educational, Vehicle, Animal, Weapon, Other",\n'
    '  "print_type": "Một trong: FDM, Resin, Unknown",\n'
    '  "keywords": ["từ khoá 1", "từ khoá 2"]\n'
    "}"
)

USER_PROMPT_TEMPLATE = (
    "Phân tích model 3D sau:\n"
    "- Filename: {filename}\n"
    "- Face count: {face_count:,}\n"
    "- Pre-supported: {is_presupported}\n"
    "- Bounding box: {bbox_x:.1f}mm × {bbox_y:.1f}mm × {bbox_z:.1f}mm\n"
    "- Nội dung tin nhắn gốc: {message_text}\n\n"
    "Chỉ trả về JSON object."
)


@dataclass
class AITagResult:
    """Structured result from the Ollama AI tagger."""

    predicted_name: str = "Unknown"
    studio: Optional[str] = None
    category: str = "Other"
    print_type: str = "Unknown"
    keywords: List[str] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)


async def tag_model(
    filename: str,
    face_count: int = 0,
    bbox: tuple[float, float, float] = (0.0, 0.0, 0.0),
    message_text: str = "",
    is_presupported: bool = False,
) -> AITagResult:
    """Call Ollama API and parse structured tags for a 3D model."""
    heuristic_studio = detect_known_studio(filename, message_text)

    env_settings = get_settings()
    from app.services.settings import SettingsService

    ollama_base_url = await SettingsService.get_setting("OLLAMA_BASE_URL", env_settings.OLLAMA_BASE_URL)
    ollama_model = await SettingsService.get_setting("OLLAMA_MODEL", env_settings.OLLAMA_MODEL)

    bbox_x, bbox_y, bbox_z = bbox

    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename,
        face_count=face_count,
        is_presupported="Có" if is_presupported else "Không",
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

    base_url_clean = (ollama_base_url or "").rstrip("/")
    if base_url_clean.endswith("/v1"):
        base_url_clean = base_url_clean[:-3]

    url = f"{base_url_clean}/v1/chat/completions"

    try:
        logger.info(f"[{filename}] Sending context to LLM: {json.dumps(payload, ensure_ascii=False)}")
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            return AITagResult(studio=heuristic_studio, raw_response=full_debug_info)

        detected_studio = parsed.get("studio") or heuristic_studio

        return AITagResult(
            predicted_name=parsed.get("predicted_name", "Unknown"),
            studio=detected_studio,
            category=parsed.get("category", "Other"),
            print_type=parsed.get("print_type", "Unknown"),
            keywords=parsed.get("keywords", []),
            raw_response=full_debug_info,
        )

    except Exception as e:
        logger.warning(f"Ollama tagging fallback for {filename!r}: {e}")
        return AITagResult(studio=heuristic_studio)
