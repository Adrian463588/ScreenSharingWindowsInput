import ctypes
from ctypes import wintypes
import time
import win32service
import win32con

def ensure_desktop_attached():
    try:
        hwinsta = win32service.OpenWindowStation('WinSta0', False, win32con.MAXIMUM_ALLOWED)
        hwinsta.SetProcessWindowStation()
        hdesk = win32service.OpenDesktop('Default', 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
    except Exception:
        pass

user32 = ctypes.windll.user32

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT)
        ]
    _anonymous_ = ("_u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_u", _INPUT_UNION)
    ]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0009
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_Z = 0x5A
KEYEVENTF_KEYUP = 0x0002

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL

class InputInjector:
    def __init__(self):
        ensure_desktop_attached()
        self.is_pressed = False
        self.last_pos = (0, 0)

    def _normalize_abs(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        screen_w = max(1, user32.GetSystemMetrics(0))
        screen_h = max(1, user32.GetSystemMetrics(1))
        abs_x = int(screen_x * 65535 / (screen_w - 1))
        abs_y = int(screen_y * 65535 / (screen_h - 1))
        return abs_x, abs_y

    def to_screen_coords(self, norm_x: float, norm_y: float, rect: dict) -> tuple[int, int]:
        """Convert normalized (0.0 to 1.0) tablet coordinates to desktop screen pixels"""
        norm_x = max(0.0, min(1.0, float(norm_x)))
        norm_y = max(0.0, min(1.0, float(norm_y)))
        screen_x = int(rect['left'] + norm_x * rect['width'])
        screen_y = int(rect['top'] + norm_y * rect['height'])
        return screen_x, screen_y

    def move(self, screen_x: int, screen_y: int):
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        self.last_pos = (screen_x, screen_y)

    def click(self, screen_x: int, screen_y: int, button: str = 'left'):
        """Send an atomic, clean click at exact coordinates without any drag jitter"""
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        self.last_pos = (screen_x, screen_y)
        abs_x, abs_y = self._normalize_abs(screen_x, screen_y)

        down_flag = MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP

        inp_down = INPUT(type=INPUT_MOUSE)
        inp_down.mi.dx = abs_x
        inp_down.mi.dy = abs_y
        inp_down.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | down_flag

        inp_up = INPUT(type=INPUT_MOUSE)
        inp_up.mi.dx = abs_x
        inp_up.mi.dy = abs_y
        inp_up.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | up_flag

        inputs = (INPUT * 2)(inp_down, inp_up)
        user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        self.is_pressed = False

    def double_click(self, screen_x: int, screen_y: int):
        self.click(screen_x, screen_y, 'left')
        time.sleep(0.05)
        self.click(screen_x, screen_y, 'left')

    def down(self, screen_x: int, screen_y: int, button: str = 'left'):
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        self.last_pos = (screen_x, screen_y)
        self.is_pressed = True
        abs_x, abs_y = self._normalize_abs(screen_x, screen_y)

        flag = MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | flag
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def drag(self, screen_x: int, screen_y: int):
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        self.last_pos = (screen_x, screen_y)
        abs_x, abs_y = self._normalize_abs(screen_x, screen_y)

        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def up(self, screen_x: int, screen_y: int, button: str = 'left'):
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        self.last_pos = (screen_x, screen_y)
        self.is_pressed = False
        abs_x, abs_y = self._normalize_abs(screen_x, screen_y)

        flag = MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | flag
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def scroll(self, screen_x: int, screen_y: int, delta_y: int):
        """Move cursor over the target window first, then send wheel event"""
        ensure_desktop_attached()
        user32.SetCursorPos(screen_x, screen_y)
        abs_x, abs_y = self._normalize_abs(screen_x, screen_y)

        wheel_amount = int(delta_y * 120)
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.mouseData = wintypes.DWORD(wheel_amount if wheel_amount >= 0 else (1 << 32) + wheel_amount)
        inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_WHEEL
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def send_undo(self):
        """Send Ctrl+Z to undo signature stroke in browser"""
        ensure_desktop_attached()
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_Z, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_Z, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def send_escape(self):
        """Send Escape key"""
        ensure_desktop_attached()
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
