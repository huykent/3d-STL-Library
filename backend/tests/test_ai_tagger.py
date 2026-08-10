"""Tests for AI tagger service (Ollama API).

All HTTP calls are mocked via httpx patch — no real Ollama connection needed.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai_tagger import tag_model, AITagResult


MOCK_OLLAMA_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": '{"predicted_name": "Dragon Figurine", "category": "Figurine", "print_type": "Resin", "keywords": ["dragon", "fantasy", "figurine"]}'
            }
        }
    ]
}


@pytest.mark.asyncio
async def test_tag_model_returns_ai_tag_result():
    """Happy path: Ollama returns valid JSON → AITagResult is populated."""
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_OLLAMA_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post.return_value = mock_response

    with patch("app.services.ai_tagger.httpx.AsyncClient", return_value=mock_client):
        result = await tag_model(
            filename="dragon.stl",
            face_count=500_000,
            bbox=(120.5, 80.3, 95.1),
        )

    assert isinstance(result, AITagResult)
    assert result.predicted_name == "Dragon Figurine"
    assert result.category == "Figurine"
    assert result.print_type == "Resin"
    assert "dragon" in result.keywords
    assert isinstance(result.raw_response, dict)


@pytest.mark.asyncio
async def test_tag_model_handles_invalid_json_gracefully():
    """If Ollama returns malformed JSON content, return a fallback AITagResult."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "not valid json at all {{ brokenbroken"}}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post.return_value = mock_response

    with patch("app.services.ai_tagger.httpx.AsyncClient", return_value=mock_client):
        result = await tag_model("unknown.stl", 100, (10.0, 10.0, 10.0))

    assert isinstance(result, AITagResult)
    assert result.predicted_name == "Unknown"


@pytest.mark.asyncio
async def test_tag_model_handles_http_error_gracefully():
    """If HTTP call fails, return a fallback AITagResult rather than crashing."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post.side_effect = httpx.RequestError(
        "connection refused", request=MagicMock()
    )

    with patch("app.services.ai_tagger.httpx.AsyncClient", return_value=mock_client):
        result = await tag_model("unknown.stl", 100, (10.0, 10.0, 10.0))

    assert isinstance(result, AITagResult)
    assert result.predicted_name == "Unknown"
    assert result.keywords == []


@pytest.mark.asyncio
async def test_tag_model_sends_correct_payload():
    """Verify the payload sent to Ollama contains the right model data."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"predicted_name":"Test","category":"Other","print_type":"FDM","keywords":[]}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post.return_value = mock_response

    with patch("app.services.ai_tagger.httpx.AsyncClient", return_value=mock_client):
        await tag_model("my_model.stl", 5000, (50.0, 30.0, 20.0))

    # Verify post was called with a payload containing the filename
    call_args = mock_client.post.call_args
    payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
    messages = payload["messages"]
    user_message = next(m for m in messages if m["role"] == "user")
    assert "my_model.stl" in user_message["content"]
    assert "5,000" in user_message["content"]
