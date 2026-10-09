import json
import os
import re
import shutil
import socket
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRCPY_DEFAULT_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-win64-v3.1.zip"
)
BIN_DIR = Path(__file__).parent / "bin" / "scrcpy"
CONFIG_WIRELESS_PATH = Path(__file__).parent / "config_wireless.json"

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


def parse_adb_devices_output(output: str) -> List[Dict[str, str]]:
    """Parse output of 'adb devices -l' into structured device records."""
    if not output:
        return []

    lines = output.splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if "List of devices attached" in line:
            header_idx = i
            break

    candidate_lines = lines[header_idx + 1:] if header_idx != -1 else lines
    devices = []
    valid_states = {"device", "unauthorized", "offline", "recovery", "bootloader", "authorizing"}

    for line in candidate_lines:
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("adb"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            state = parts[1]
            if state in valid_states:
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


def get_adb_devices(timeout: int = 10) -> List[Dict[str, str]]:
    """List connected Android devices via adb with retry on daemon startup."""
    adb_bin = find_adb()
    if not adb_bin:
        return []

    try:
        res = subprocess.run(
            [adb_bin, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        combined = res.stdout + "\n" + res.stderr
        if "daemon started successfully" in combined and not res.stdout.strip():
            res = subprocess.run(
                [adb_bin, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        return parse_adb_devices_output(res.stdout)
    except Exception:
        return []


def load_remembered_hosts() -> List[str]:
    """Load previously connected wireless ADB hosts."""
    if CONFIG_WIRELESS_PATH.exists():
        try:
            data = json.loads(CONFIG_WIRELESS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(h) for h in data if h]
        except Exception:
            pass
    return ["192.168.43.1:5555", "192.168.0.2:5555"]


def save_remembered_host(target: str) -> None:
    """Save newly connected wireless ADB host for future auto-discovery."""
    hosts = load_remembered_hosts()
    if target not in hosts:
        hosts.append(target)
        try:
            CONFIG_WIRELESS_PATH.write_text(json.dumps(hosts, indent=2), encoding="utf-8")
        except Exception:
            pass


def remove_remembered_host(target: str) -> None:
    """Remove a wireless ADB host from remembered list."""
    hosts = load_remembered_hosts()
    if target in hosts:
        hosts = [h for h in hosts if h != target]
        try:
            CONFIG_WIRELESS_PATH.write_text(json.dumps(hosts, indent=2), encoding="utf-8")
        except Exception:
            pass


def find_open_adb_hosts() -> List[str]:
    """Fast probe of candidate wireless IPs (remembered, hotspot, and ARP table) on port 5555."""
    candidates = set(load_remembered_hosts())

    gw = get_wifi_gateway_ip()
    if gw:
        candidates.add(f"{gw}:5555")
    candidates.add("192.168.43.1:5555")

    try:
        res = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=2, check=False
        )
        found_ips = re.findall(r"(?:192\.168|10\.\d+|172\.\d+)\.\d+\.\d+", res.stdout)
        for ip in found_ips:
            if not ip.endswith(".255") and not ip.endswith(".1"):
                candidates.add(f"{ip}:5555")
    except Exception:
        pass

    open_hosts = []
    for cand in candidates:
        if ":" in cand:
            host, p_str = cand.rsplit(":", 1)
            try:
                port = int(p_str)
            except ValueError:
                port = 5555
        else:
            host, port = cand, 5555

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            if s.connect_ex((host, port)) == 0:
                open_hosts.append(f"{host}:{port}")
            s.close()
        except Exception:
            pass

    return open_hosts


def auto_detect_devices() -> List[Dict[str, str]]:
    """Automatically detect all connected USB and Wireless ADB devices.
    Discovers and connects to open ADB Wireless endpoints on LAN & Mobile Hotspot.
    """
    devices = get_adb_devices()
    adb_bin = find_adb()
    if not adb_bin:
        return devices

    connected_serials = {d["serial"] for d in devices}
    open_hosts = find_open_adb_hosts()

    new_connection = False
    for target in open_hosts:
        if target not in connected_serials:
            try:
                subprocess.run(
                    [adb_bin, "connect", target],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                new_connection = True
            except Exception:
                pass

    if new_connection:
        devices = get_adb_devices()

    return devices


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

    # Provide consistent ADB executable path to avoid version mismatch
    env = os.environ.copy()
    adb_bin = find_adb()
    if adb_bin:
        env["ADB"] = adb_bin

    # Launch subprocess
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(scrcpy_bin),
        env=env,
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
        "devices": auto_detect_devices(),
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
        if success:
            save_remembered_host(target)
        return {
            "status": "ok" if success else "error",
            "target": target,
            "message": out,
            "devices": auto_detect_devices(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "target": target,
            "message": str(exc),
            "devices": auto_detect_devices(),
        }


def disconnect_adb_wireless(target: str) -> Dict[str, Any]:
    """Disconnect ADB wireless session."""
    target = target.strip()
    if not target:
        raise ValueError("Target perangkat tidak boleh kosong")
    remove_remembered_host(target)
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
            "devices": auto_detect_devices(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "target": target,
            "message": str(exc),
            "devices": auto_detect_devices(),
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
