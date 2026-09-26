import pytest
from starlette.testclient import TestClient
from server import app, capturer, injector

def test_screen_capturer_frame():
    jpeg_bytes, rect = capturer.grab_jpeg()
    assert len(jpeg_bytes) > 500, "JPEG frame should have content"
    assert rect["width"] > 0
    assert rect["height"] > 0

def test_injector_coords():
    rect = {"left": 100, "top": 200, "width": 1000, "height": 800}
    
    # Center
    sx, sy = injector.to_screen_coords(0.5, 0.5, rect)
    assert sx == 600
    assert sy == 600

    # Top-left
    sx, sy = injector.to_screen_coords(0.0, 0.0, rect)
    assert sx == 100
    assert sy == 200

    # Clamping out-of-bounds
    sx, sy = injector.to_screen_coords(-0.2, 1.5, rect)
    assert sx == 100
    assert sy == 1000

def test_injector_click_and_scroll():
    # Verify click and scroll execute without throwing exceptions
    injector.click(500, 500, 'left')
    injector.scroll(500, 500, 1)
    injector.double_click(500, 500)
    assert True

def test_api_endpoints():
    client = TestClient(app)
    
    # Tablet page
    r = client.get("/")
    assert r.status_code == 200
    assert "TabSign" in r.text
    
    # Host dashboard
    r = client.get("/host")
    assert r.status_code == 200
    assert "TabSign Windows Host" in r.text

    # Status API
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "ip" in data
    assert "port" in data
    assert data["port"] == 8000

    # Windows API
    r = client.get("/api/windows")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # QR Code API
    r = client.get("/api/qrcode")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 100
