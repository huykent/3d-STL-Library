import pytest
from app.telegram.client import get_telegram_client

def test_telegram_client_singleton():
    client1 = get_telegram_client()
    client2 = get_telegram_client()
    assert client1 is client2
    assert client1.api_id is not None
