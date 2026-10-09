import asyncio
import io
import json
import socket
from typing import Set, Optional
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import qrcode
import psutil

from capture import ScreenCapturer, attach_to_default_desktop
from injector import InputInjector
import scrcpy_manager

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(stream_worker())
    # Background auto-download of scrcpy if missing on Windows
    if not scrcpy_manager.find_scrcpy():
        asyncio.create_task(asyncio.to_thread(scrcpy_manager.ensure_scrcpy))
    yield
    worker_task.cancel()

app = FastAPI(title="TabSign Server", lifespan=lifespan)

# Initialize modules
attach_to_default_desktop()
capturer = ScreenCapturer()
injector = InputInjector()

# Connected tablet clients
connected_clients: Set[WebSocket] = set()

# Streaming configuration
target_fps = 30
server_port = 8000

def get_best_local_ip() -> str:
    """Find the best local Wi-Fi or Ethernet IPv4 address"""
    candidates = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                ip = addr.address
                # Priority: Wi-Fi, then private subnets (192.168, 10., 172.)
                if not ip.startswith("169.254."):
                    is_wifi = "wi-fi" in iface.lower() or "wlan" in iface.lower()
                    candidates.append((10 if is_wifi else 5, ip))
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    # Fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

local_ip = get_best_local_ip()
server_url = f"http://{local_ip}:{server_port}"

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.get("/host")
async def get_host_page():
    return FileResponse("static/host.html")

@app.get("/api/status")
async def get_status():
    return {
        "ip": local_ip,
        "port": server_port,
        "url": server_url,
        "mode": capturer.mode,
        "target_hwnd": capturer.target_hwnd,
        "quality": capturer.quality,
        "fps": target_fps,
        "connected_clients": len(connected_clients)
    }

@app.get("/api/windows")
async def get_windows():
    return capturer.get_visible_windows()

@app.post("/api/config")
async def update_config(config: dict):
    global target_fps
    if "hwnd" in config:
        hwnd = config["hwnd"]
        capturer.set_target_window(hwnd if hwnd != 0 else None)
    if "quality" in config:
        capturer.quality = max(30, min(95, int(config["quality"])))
    if "fps" in config:
        target_fps = max(10, min(60, int(config["fps"])))
    return {"status": "ok", "mode": capturer.mode, "fps": target_fps, "quality": capturer.quality}

@app.get("/api/qrcode")
async def get_qrcode():
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(server_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/api/android/devices")
async def get_android_devices():
    return await asyncio.to_thread(scrcpy_manager.auto_detect_devices)

@app.get("/api/android/devices/scan")
async def scan_android_devices():
    return await asyncio.to_thread(scrcpy_manager.auto_detect_devices)

@app.get("/api/android/scrcpy/status")
async def get_android_scrcpy_status():
    return await asyncio.to_thread(scrcpy_manager.get_scrcpy_status)

@app.post("/api/android/scrcpy/install")
async def install_android_scrcpy():
    try:
        path = await asyncio.to_thread(scrcpy_manager.ensure_scrcpy)
        return {"status": "ok", "path": path}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

@app.post("/api/android/scrcpy/start")
async def start_android_scrcpy(payload: Optional[dict] = None):
    payload = payload or {}
    serial = payload.get("serial")
    stay_awake = payload.get("stay_awake", True)
    turn_screen_off = payload.get("turn_screen_off", False)
    max_size = payload.get("max_size")
    try:
        await asyncio.to_thread(
            scrcpy_manager.launch_scrcpy,
            serial=serial,
            stay_awake=stay_awake,
            turn_screen_off=turn_screen_off,
            max_size=max_size,
        )
        return {"status": "ok", "running": True, "serial": serial}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

@app.post("/api/android/scrcpy/stop")
async def stop_android_scrcpy():
    stopped = scrcpy_manager.stop_scrcpy()
    return {"status": "ok", "stopped": stopped}

@app.post("/api/android/adb/connect")
async def adb_connect(payload: dict):
    ip = payload.get("ip", "")
    port = int(payload.get("port", 5555))
    if not ip:
        return {"status": "error", "message": "Alamat IP tidak boleh kosong"}
    res = await asyncio.to_thread(scrcpy_manager.connect_adb_wireless, ip=ip, port=port)
    return res

@app.post("/api/android/adb/disconnect")
async def adb_disconnect(payload: dict):
    target = payload.get("target", "")
    if not target:
        return {"status": "error", "message": "Target tidak boleh kosong"}
    res = await asyncio.to_thread(scrcpy_manager.disconnect_adb_wireless, target=target)
    return res

@app.post("/api/android/adb/tcpip")
async def adb_enable_tcpip(payload: Optional[dict] = None):
    payload = payload or {}
    port = int(payload.get("port", 5555))
    serial = payload.get("serial")
    res = await asyncio.to_thread(scrcpy_manager.enable_adb_tcpip, port=port, serial=serial)
    return res

@app.get("/api/android/adb/gateway")
async def get_adb_gateway():
    gw = await asyncio.to_thread(scrcpy_manager.get_wifi_gateway_ip)
    return {"gateway": gw, "hotspot_default": "192.168.43.1"}

# Background Screen Streaming Worker
async def stream_worker():
    global target_fps
    while True:
        try:
            if connected_clients:
                frame_interval = 1.0 / target_fps
                t0 = asyncio.get_event_loop().time()
                
                # Capture frame in thread to avoid blocking asyncio loop
                jpeg_bytes, current_rect = await asyncio.to_thread(capturer.grab_jpeg)
                
                # Broadcast binary frame to all connected tablet clients
                disconnected = set()
                for client in connected_clients:
                    try:
                        await client.send_bytes(jpeg_bytes)
                    except Exception:
                        disconnected.add(client)
                        
                for dc in disconnected:
                    connected_clients.discard(dc)
                
                elapsed = asyncio.get_event_loop().time() - t0
                sleep_time = max(0.001, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0.15)
        except Exception:
            await asyncio.sleep(0.1)

@app.websocket("/ws/client")
async def websocket_client_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        # Send initial capture rect to client
        rect = capturer.get_capture_rect()
        await websocket.send_text(json.dumps({"type": "rect", "rect": rect}))
        
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            event_type = data.get("type")
            
            rect = capturer.get_capture_rect()
            
            if event_type == "click":
                u = float(data.get("x", 0.5))
                v = float(data.get("y", 0.5))
                button = data.get("button", "left")
                screen_x, screen_y = injector.to_screen_coords(u, v, rect)
                injector.click(screen_x, screen_y, button)
                
            elif event_type == "double_click":
                u = float(data.get("x", 0.5))
                v = float(data.get("y", 0.5))
                screen_x, screen_y = injector.to_screen_coords(u, v, rect)
                injector.double_click(screen_x, screen_y)
                
            elif event_type in ["down", "drag", "move", "up"]:
                u = float(data.get("x", 0.5))
                v = float(data.get("y", 0.5))
                button = data.get("button", "left")
                screen_x, screen_y = injector.to_screen_coords(u, v, rect)
                
                if event_type == "down":
                    injector.down(screen_x, screen_y, button)
                elif event_type in ["drag", "move"]:
                    injector.drag(screen_x, screen_y)
                elif event_type == "up":
                    injector.up(screen_x, screen_y, button)
                    
            elif event_type == "scroll":
                u = float(data.get("x", 0.5))
                v = float(data.get("y", 0.5))
                delta = int(data.get("delta", 0))
                screen_x, screen_y = injector.to_screen_coords(u, v, rect)
                injector.scroll(screen_x, screen_y, delta)
                
            elif event_type == "undo":
                injector.send_undo()
                
            elif event_type == "esc":
                injector.send_escape()
                
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception:
        connected_clients.discard(websocket)

def generate_terminal_qr(data: str, border: int = 2) -> str:
    """Generate compact, high-contrast, non-truncated ASCII QR code for terminals.
    Uses half-block unicode characters with proper quiet zone so camera scanners
    can reliably decode the QR code on dark or light terminals without overflowing
    standard 24-line terminal windows.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    h = len(matrix)
    w = len(matrix[0])

    if h % 2 != 0:
        matrix.append([False] * w)
        h += 1

    lines = []
    for r in range(0, h, 2):
        row_str = []
        for c in range(w):
            top_white = not matrix[r][c]
            bot_white = not matrix[r + 1][c]
            if top_white and bot_white:
                row_str.append("█")
            elif top_white and not bot_white:
                row_str.append("▀")
            elif not top_white and bot_white:
                row_str.append("▄")
            else:
                row_str.append(" ")
        lines.append("".join(row_str))
    return "\n".join(lines)

def format_banner(url: str, port: int) -> str:
    """Format compact banner guaranteed to fit inside standard 24-line terminal viewport."""
    qr_art = generate_terminal_qr(url, border=2)
    lines = [
        "=" * 56,
        "  📱 TabSign - Screen Mirroring & S-Pen Signature Input",
        f"  Target URL: {url}",
        f"  Host Panel: http://localhost:{port}/host",
        "=" * 56,
        qr_art,
        "  Arahkan kamera tablet / HP ke QR Code di atas",
        "=" * 56,
    ]
    return "\n".join(lines)

def print_banner():
    print(format_banner(server_url, server_port))

if __name__ == "__main__":
    print_banner()
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="warning")
