import pytest
from fastapi.testclient import TestClient
from app.main import app as fastapi_app

def test_health_endpoint():
    # Just ensures the app doesn't crash on startup with the new lifespan
    # TestClient triggers the lifespan context manager
    with TestClient(fastapi_app) as client:
        response = client.get("/health")
        assert response.status_code == 200
