"""
Smoke test: verify the FastAPI /health endpoint responds correctly.
Requires a running uvicorn server on port 8000.
Run as: pytest tests/test_health.py -v -m integration
"""
import http.client
import pytest


@pytest.mark.integration
def test_health_endpoint_returns_ok():
    """GET /health must return 200 with status='ok'."""
    import json
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
    conn.request("GET", "/health")
    response = conn.getresponse()
    body = response.read().decode()
    data = json.loads(body)

    assert response.status == 200, f"Expected 200, got {response.status}"
    assert data.get("status") == "ok", f"Expected status='ok', got: {data}"
    assert "env" in data, f"Expected 'env' key in response, got: {data}"
