import http.client
import sys

try:
    c = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
    c.request("GET", "/health")
    r = c.getresponse()
    body = r.read().decode()
    print(f"STATUS: {r.status}")
    print(f"BODY: {body}")
    assert r.status == 200, f"Expected 200, got {r.status}"
    assert "ok" in body, f"Expected 'ok' in body, got: {body}"
    print("HEALTH CHECK PASSED")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
