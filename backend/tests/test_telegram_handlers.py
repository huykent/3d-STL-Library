import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.telegram.handlers import handle_new_message

@pytest.mark.asyncio
async def test_handle_new_message_with_stl():
    # Mock a telethon message with an .stl document
    event_mock = AsyncMock()
    event_mock.message = MagicMock()
    event_mock.message.id = 12345
    event_mock.chat_id = -100123456
    
    document_mock = MagicMock()
    attr_mock = MagicMock()
    attr_mock.file_name = "test_model.stl"
    document_mock.attributes = [attr_mock]
    event_mock.message.document = document_mock

    # Mock the Redis queue
    with patch('app.telegram.handlers.get_redis_pool', new_callable=AsyncMock) as mock_get_redis:
        redis_mock = AsyncMock()
        mock_get_redis.return_value = redis_mock
        
        await handle_new_message(event_mock)
        
        redis_mock.enqueue_job.assert_called_once_with(
            'process_telegram_message',
            message_id=12345,
            chat_id=-100123456
        )

@pytest.mark.asyncio
async def test_handle_new_message_ignored_extension():
    # Mock a telethon message with an .txt document
    event_mock = AsyncMock()
    event_mock.message = MagicMock()
    event_mock.message.id = 12346
    event_mock.chat_id = -100123456
    
    document_mock = MagicMock()
    attr_mock = MagicMock()
    attr_mock.file_name = "readme.txt"
    document_mock.attributes = [attr_mock]
    event_mock.message.document = document_mock

    with patch('app.telegram.handlers.get_redis_pool', new_callable=AsyncMock) as mock_get_redis:
        redis_mock = AsyncMock()
        mock_get_redis.return_value = redis_mock
        
        await handle_new_message(event_mock)
        
        # Should not be called
        redis_mock.enqueue_job.assert_not_called()
