import cv2
import numpy as np
from starlette.testclient import TestClient
from server import app, capturer, injector, generate_terminal_qr, format_banner

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

def test_terminal_qr_dimensions_and_fit():
    """BDD/SDD Scenario: Terminal QR fits standard 24-line console without truncation.
    Given a target server URL,
    When generate_terminal_qr is invoked,
    Then the line count must be <= 16 and column count <= 40 to fit 80x24 terminal.
    """
    url = "http://192.168.0.5:8000"
    qr_text = generate_terminal_qr(url, border=2)
    lines = qr_text.splitlines()
    assert len(lines) <= 16, f"QR height ({len(lines)} lines) exceeds maximum 16 lines for 24-line terminal"
    assert all(len(line) <= 40 for line in lines), "QR width exceeds 40 columns"

def test_terminal_qr_camera_decodable():
    """BDD/SDD Scenario: Terminal QR is decodable by camera / computer vision detector.
    Given the generated ASCII QR art,
    When rendered to pixel matrix and inspected by OpenCV QRCodeDetector,
    Then the decoded data must match the exact URL without any truncation.
    """
    url = "http://192.168.0.5:8000"
    qr_text = generate_terminal_qr(url, border=2)
    lines = qr_text.splitlines()

    recon = []
    for line in lines:
        rt, rb = [], []
        for ch in line:
            if ch == "█":
                rt.append(255)
                rb.append(255)
            elif ch == "▀":
                rt.append(255)
                rb.append(0)
            elif ch == "▄":
                rt.append(0)
                rb.append(255)
            else:
                rt.append(0)
                rb.append(0)
        recon.append(rt)
        recon.append(rb)

    img = np.array(recon, dtype=np.uint8)
    img_scaled = cv2.resize(img, (img.shape[1] * 10, img.shape[0] * 10), interpolation=cv2.INTER_NEAREST)
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img_scaled)
    assert data == url, f"Decoded data '{data}' does not match expected '{url}'"

def test_format_banner_fits_viewport():
    """BDD/SDD Scenario: Entire startup banner fits standard 24-line terminal viewport.
    Given server URL and port,
    When format_banner is generated,
    Then total lines must be <= 23 so no scrolling/truncation occurs in terminal.
    """
    banner = format_banner("http://192.168.0.5:8000", 8000)
    lines = banner.splitlines()
    assert len(lines) <= 23, f"Banner has {len(lines)} lines, which overflows standard 24-line terminal"
