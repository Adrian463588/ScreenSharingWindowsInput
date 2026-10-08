import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRCPY_DEFAULT_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-win64-v3.1.zip"
)
BIN_DIR = Path(__file__).parent / "bin" / "scrcpy"

# Global reference to running scrcpy process
_active_process: Optional[subprocess.Popen] = None
_active_serial: Optional[str] = None


def get_bin_dir() -> Path:
    return BIN_DIR


def find_adb() -> Optional[str]:
    """Find adb executable on system PATH or local scrcpy folder."""
    adb_path = shutil.which("adb")
    if adb_path:
        return adb_path
    if BIN_DIR.exists():
        direct = BIN_DIR / "adb.exe"
        if direct.exists():
            return str(direct)
        for child in BIN_DIR.rglob("adb.exe"):
            return str(child)
    return None


def ensure_adb() -> str:
    """Ensure adb executable is available, downloading scrcpy bundle if missing."""
    adb_bin = find_adb()
    if adb_bin:
        return adb_bin
    ensure_scrcpy()
    adb_bin = find_adb()
    if not adb_bin:
        raise FileNotFoundError("adb executable could not be found or downloaded")
    return adb_bin


def find_scrcpy() -> Optional[str]:
    """Find scrcpy.exe on system PATH or in local bin folder."""
    # 1. System PATH
    system_scrcpy = shutil.which("scrcpy")
    if system_scrcpy:
        return system_scrcpy

    # 2. Local BIN_DIR
    if BIN_DIR.exists():
        direct = BIN_DIR / "scrcpy.exe"
        if direct.exists():
            return str(direct)
        for child in BIN_DIR.rglob("scrcpy.exe"):
            return str(child)
    return None


def get_latest_scrcpy_url() -> str:
    """Fetch latest scrcpy release URL from GitHub API with fallback."""
    api_url = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if "win64" in name and name.endswith(".zip"):
                    return str(asset.get("browser_download_url"))
    except Exception:
        pass
    return SCRCPY_DEFAULT_URL


def ensure_scrcpy(url: Optional[str] = None) -> str:
    """Ensure scrcpy is available; download and safely extract if missing."""
    existing = find_scrcpy()
    if existing:
        return existing

    download_url = url or get_latest_scrcpy_url()
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    temp_zip = BIN_DIR.parent / "scrcpy_temp.zip"

    # Download
    req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(temp_zip, "wb") as out:
        shutil.copyfileobj(resp, out)

    # Safe extraction (guard against Zip Slip vulnerability)
    with zipfile.ZipFile(temp_zip, "r") as zf:
        resolved_bin = BIN_DIR.resolve()
        for member in zf.infolist():
            target_path = (BIN_DIR / member.filename).resolve()
            if not str(target_path).startswith(str(resolved_bin)):
                raise ValueError(f"Zip slip attempt detected in {member.filename}")
        zf.extractall(BIN_DIR)

    if temp_zip.exists():
        temp_zip.unlink()

    # Locate extracted scrcpy.exe
    installed = find_scrcpy()
    if not installed:
        raise FileNotFoundError("scrcpy.exe not found after extraction")
    return installed


def get_adb_devices() -> List[Dict[str, str]]:
    """List connected Android devices via adb."""
    adb_bin = find_adb()
    if not adb_bin:
        return []

    try:
        res = subprocess.run(
            [adb_bin, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        devices = []
        for line in res.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                model = ""
                product = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                    elif p.startswith("product:"):
                        product = p.split(":", 1)[1]
                devices.append({
                    "serial": serial,
                    "state": state,
                    "model": model or serial,
                    "product": product,
                })
        return devices
    except Exception:
        return []


def is_scrcpy_running() -> bool:
    global _active_process
    if _active_process is None:
        return False
    if _active_process.poll() is not None:
        _active_process = None
        return False
    return True


def launch_scrcpy(
    serial: Optional[str] = None,
    stay_awake: bool = True,
    turn_screen_off: bool = False,
    max_size: Optional[int] = None,
) -> subprocess.Popen:
    """Launch scrcpy for the specified or first available Android device."""
    global _active_process, _active_serial

    if is_scrcpy_running():
        return _active_process  # type: ignore

    scrcpy_bin = ensure_scrcpy()

    # Determine target serial
    devices = get_adb_devices()
    target_serial = serial
    if not target_serial and devices:
        target_serial = devices[0]["serial"]

    cmd = [scrcpy_bin]
    if target_serial:
        cmd.extend(["-s", target_serial])
    if stay_awake:
        cmd.append("--stay-awake")
    if turn_screen_off:
        cmd.append("--turn-screen-off")
    if max_size and max_size > 0:
        cmd.extend(["--max-size", str(max_size)])

    # Add window title
    cmd.extend(["--window-title", f"TabSign Android Mirror: {target_serial or 'Device'}"])

    # Launch subprocess
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(scrcpy_bin),
    )
    _active_process = proc
    _active_serial = target_serial
    return proc


def stop_scrcpy() -> bool:
    """Stop active scrcpy process."""
    global _active_process, _active_serial
    if _active_process and _active_process.poll() is None:
        try:
            _active_process.terminate()
            _active_process.wait(timeout=2)
        except Exception:
            _active_process.kill()
        _active_process = None
        _active_serial = None
        return True
    _active_process = None
    _active_serial = None
    return False


def get_scrcpy_status() -> Dict[str, Any]:
    """Get status of scrcpy and connected Android devices."""
    installed_path = find_scrcpy()
    running = is_scrcpy_running()
    return {
        "installed": installed_path is not None,
        "path": installed_path,
        "running": running,
        "active_serial": _active_serial if running else None,
        "pid": _active_process.pid if running and _active_process else None,
        "devices": get_adb_devices(),
        "wifi_gateway": get_wifi_gateway_ip(),
    }


def normalize_adb_target(ip: str, port: int = 5555) -> str:
    """Normalize IP and port string for adb wireless connection."""
    ip = ip.strip()
    if not ip:
        raise ValueError("Alamat IP tidak boleh kosong")
    if ":" in ip:
        host, p_str = ip.rsplit(":", 1)
        try:
            p = int(p_str)
            return f"{host}:{p}"
        except ValueError:
            return f"{ip}:{port}"
    return f"{ip}:{port}"


def connect_adb_wireless(ip: str, port: int = 5555) -> Dict[str, Any]:
    """Connect to Android device via ADB Wireless (LAN Wi-Fi or Phone Hotspot)."""
    target = normalize_adb_target(ip, port)
    adb_bin = ensure_adb()

    try:
        res = subprocess.run(
            [adb_bin, "connect", target],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        out = (res.stdout + " " + res.stderr).strip()
        lower = out.lower()
        success = "connected" in lower and "cannot" not in lower and "failed" not in lower
        return {
            "status": "ok" if success else "error",
            "target": target,
            "message": out,
            "devices": get_adb_devices(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "target": target,
            "message": str(exc),
            "devices": get_adb_devices(),
        }


def disconnect_adb_wireless(target: str) -> Dict[str, Any]:
    """Disconnect ADB wireless session."""
    target = target.strip()
    if not target:
        raise ValueError("Target perangkat tidak boleh kosong")
    adb_bin = find_adb()
    if not adb_bin:
        return {"status": "error", "message": "ADB tidak ditemukan", "devices": []}

    try:
        res = subprocess.run(
            [adb_bin, "disconnect", target],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        out = (res.stdout + " " + res.stderr).strip()
        return {
            "status": "ok",
            "target": target,
            "message": out,
            "devices": get_adb_devices(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "target": target,
            "message": str(exc),
            "devices": get_adb_devices(),
        }


def enable_adb_tcpip(port: int = 5555, serial: Optional[str] = None) -> Dict[str, Any]:
    """Enable ADB over TCP/IP mode on connected USB device."""
    adb_bin = ensure_adb()
    cmd = [adb_bin]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["tcpip", str(port)])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        out = (res.stdout + " " + res.stderr).strip()
        success = res.returncode == 0 or "restarting" in out.lower()
        return {
            "status": "ok" if success else "error",
            "port": port,
            "serial": serial,
            "message": out or f"Port TCP/IP {port} diaktifkan.",
            "devices": get_adb_devices(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "port": port,
            "message": str(exc),
            "devices": get_adb_devices(),
        }


def get_wifi_gateway_ip() -> Optional[str]:
    """Detect default gateway IP for active Wi-Fi or Phone Hotspot adapter."""
    try:
        res = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=4, check=False
        )
        in_wifi = False
        for line in res.stdout.splitlines():
            lower = line.lower()
            if "wireless" in lower or "wi-fi" in lower or "wlan" in lower:
                in_wifi = True
            elif "adapter" in lower:
                in_wifi = False

            if in_wifi and "default gateway" in lower:
                parts = line.split(":")
                if len(parts) > 1:
                    gw = parts[1].strip()
                    if gw and not gw.startswith("fe80") and "." in gw:
                        return gw
    except Exception:
        pass
    return None
