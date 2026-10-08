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

def test_scrcpy_manager_status_and_discovery():
    """BDD/SDD Scenario: scrcpy detection and status reporting.
    Given scrcpy_manager,
    When get_scrcpy_status is called,
    Then it returns a dictionary with installed, running, and devices keys.
    """
    import scrcpy_manager

    status = scrcpy_manager.get_scrcpy_status()
    assert isinstance(status, dict)
    assert "installed" in status
    assert "running" in status
    assert "devices" in status
    assert isinstance(status["devices"], list)

def test_api_android_endpoints():
    """BDD/SDD Scenario: Android mirroring REST endpoints.
    Given FastAPI test client,
    When calling /api/android/devices, /api/android/scrcpy/status, /api/android/scrcpy/stop,
    Then all endpoints respond with HTTP 200 and expected schema.
    """
    client = TestClient(app)

    # Devices endpoint
    r_dev = client.get("/api/android/devices")
    assert r_dev.status_code == 200
    assert isinstance(r_dev.json(), list)

    # Status endpoint
    r_stat = client.get("/api/android/scrcpy/status")
    assert r_stat.status_code == 200
    data = r_stat.json()
    assert "installed" in data
    assert "running" in data

    # Stop endpoint (safe when idle)
    r_stop = client.post("/api/android/scrcpy/stop")
    assert r_stop.status_code == 200
    assert r_stop.json()["status"] == "ok"


def test_normalize_adb_target_bdd():
    """BDD/SDD Scenario: Normalization of ADB wireless IP and port targets.
    Given various IP formats (plain IP, IP with port, padded strings),
    When normalize_adb_target is executed,
    Then target string is correctly formatted as host:port, or raises ValueError on empty.
    """
    import pytest
    import scrcpy_manager

    assert scrcpy_manager.normalize_adb_target("192.168.0.2") == "192.168.0.2:5555"
    assert scrcpy_manager.normalize_adb_target("192.168.0.2", 5556) == "192.168.0.2:5556"
    assert scrcpy_manager.normalize_adb_target("192.168.43.1:5555") == "192.168.43.1:5555"
    assert scrcpy_manager.normalize_adb_target("  192.168.43.1:8000  ") == "192.168.43.1:8000"

    with pytest.raises(ValueError):
        scrcpy_manager.normalize_adb_target("")

    with pytest.raises(ValueError):
        scrcpy_manager.normalize_adb_target("   ")


def test_wifi_gateway_detection_bdd():
    """BDD/SDD Scenario: Detection of active Wi-Fi or Phone Hotspot gateway IP.
    Given a local network environment,
    When get_wifi_gateway_ip is called,
    Then it returns None or a valid IPv4 string without crashing.
    """
    import scrcpy_manager

    gw = scrcpy_manager.get_wifi_gateway_ip()
    if gw is not None:
        assert isinstance(gw, str)
        assert "." in gw
        assert len(gw.split(".")) == 4


def test_api_adb_wireless_endpoints_bdd():
    """BDD/SDD Scenario: ADB wireless connect, disconnect, and gateway endpoints.
    Given FastAPI TestClient,
    When querying /api/android/adb/gateway and posting connect/disconnect payloads,
    Then endpoints handle inputs properly and return expected response schemas.
    """
    client = TestClient(app)

    # Gateway endpoint
    r_gw = client.get("/api/android/adb/gateway")
    assert r_gw.status_code == 200
    gw_data = r_gw.json()
    assert "hotspot_default" in gw_data
    assert gw_data["hotspot_default"] == "192.168.43.1"

    # Connect with empty IP -> error response
    r_empty_conn = client.post("/api/android/adb/connect", json={"ip": ""})
    assert r_empty_conn.status_code == 200
    assert r_empty_conn.json()["status"] == "error"

    # Disconnect with empty target -> error response
    r_empty_disc = client.post("/api/android/adb/disconnect", json={"target": ""})
    assert r_empty_disc.status_code == 200
    assert r_empty_disc.json()["status"] == "error"


def test_api_adb_tcpip_endpoint_bdd():
    """BDD/SDD Scenario: ADB TCP/IP mode activation endpoint.
    Given FastAPI TestClient,
    When posting to /api/android/adb/tcpip,
    Then the endpoint responds with HTTP 200 and status key.
    """
    client = TestClient(app)
    r_tcp = client.post("/api/android/adb/tcpip", json={"port": 5555})
    assert r_tcp.status_code == 200
    data = r_tcp.json()
    assert "status" in data
    assert "port" in data
    assert data["port"] == 5555
