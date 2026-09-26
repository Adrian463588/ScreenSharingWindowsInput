import io
import threading
from typing import Optional, List, Dict, Tuple
import win32gui
import win32service
import win32con
from PIL import Image
import mss

def attach_to_default_desktop() -> bool:
    """Ensure current thread is attached to interactive WinSta0\\Default desktop"""
    try:
        hwinsta = win32service.OpenWindowStation('WinSta0', False, win32con.MAXIMUM_ALLOWED)
        hwinsta.SetProcessWindowStation()
        hdesk = win32service.OpenDesktop('Default', 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
        return True
    except Exception as e:
        print(f"[Desktop] Notice: {e}")
        return False

class ScreenCapturer:
    def __init__(self):
        attach_to_default_desktop()
        self.lock = threading.Lock()
        self._sct = mss.MSS()
        self.mode = "screen"  # 'screen' or 'window'
        self.target_hwnd: Optional[int] = None
        self.quality = 75
        self.max_width = 1920
        self.max_height = 1080
        
    def get_monitors(self) -> List[Dict]:
        """Return list of monitors"""
        return self._sct.monitors

    def get_visible_windows(self) -> List[Dict]:
        """Return list of visible, interactive windows that have a title"""
        attach_to_default_desktop()
        windows = []
        
        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if title and w > 150 and h > 150:
                    # Ignore tooltips, program manager, etc.
                    if title not in ["Program Manager", "Settings"]:
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "rect": {"left": rect[0], "top": rect[1], "width": w, "height": h}
                        })
                        
        try:
            win32gui.EnumWindows(enum_handler, None)
        except Exception as e:
            print(f"[Capturer] Window enum error: {e}")
            
        return windows

    def set_target_window(self, hwnd: Optional[int]):
        """Set a specific window to capture, or None for full screen"""
        with self.lock:
            if hwnd and win32gui.IsWindow(hwnd):
                self.target_hwnd = hwnd
                self.mode = "window"
            else:
                self.target_hwnd = None
                self.mode = "screen"

    def get_capture_rect(self) -> Dict[str, int]:
        """Get the current capture bounding box in desktop coordinates"""
        if self.mode == "window" and self.target_hwnd and win32gui.IsWindow(self.target_hwnd):
            try:
                rect = win32gui.GetWindowRect(self.target_hwnd)
                left, top, right, bottom = rect
                w = right - left
                h = bottom - top
                if w > 0 and h > 0:
                    return {"left": max(0, left), "top": max(0, top), "width": w, "height": h}
            except Exception:
                pass
        
        # Default to primary monitor
        mon = self._sct.monitors[1] if len(self._sct.monitors) > 1 else self._sct.monitors[0]
        return {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}

    def grab_jpeg(self) -> Tuple[bytes, Dict[str, int]]:
        """
        Grab a single frame, compress to JPEG, and return (jpeg_bytes, current_rect).
        """
        attach_to_default_desktop()
        with self.lock:
            rect = self.get_capture_rect()
            sct_img = self._sct.grab(rect)
            
            # Convert raw BGRA to RGB Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Optional downscale if screen is 4K to preserve network bandwidth and tablet responsiveness
            if img.width > self.max_width or img.height > self.max_height:
                img.thumbnail((self.max_width, self.max_height), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=self.quality, optimize=False)
            return buf.getvalue(), rect
