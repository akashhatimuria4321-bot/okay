"""
tools/automation.py — JARVIS OMEGA V9 (COMPLETE)
V9 ADDITIONS:
- Advanced Mouse: double_click, right_click, drag_to, drag_rel, scroll_left/right
- Browser Automation: open_browser, fill_form
- Window Control: focus_window, list_windows, resize_window, move_window
- System Info: system_info, list_processes
- Safety checks for destructive actions
- OCR + Screen reading with EasyOCR fallback
"""
from __future__ import annotations

import os, re, subprocess, time, webbrowser, platform
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

BASE = Path(__file__).resolve().parent.parent

# ── Optional deps ──────────────────────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    PYAUTOGUI = True
except ImportError:
    PYAUTOGUI = False

try:
    import pygetwindow as gw
    PYGETWINDOW = True
except ImportError:
    PYGETWINDOW = False

try:
    from PIL import ImageGrab
    PIL = True
except ImportError:
    PIL = False

try:
    import pytesseract
    TESSERACT = True
except ImportError:
    TESSERACT = False

try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

# ══════════════════════════════════════════════════════════════════════════════
# CHROME PATH DETECTION
# ══════════════════════════════════════════════════════════════════════════════
def _find_chrome() -> Optional[str]:
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None

_CHROME_PATH = _find_chrome()

# ══════════════════════════════════════════════════════════════════════════════
# WINDOW HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _activate_window(title_pattern: str, timeout: float = 2.0) -> bool:
    if not PYGETWINDOW:
        return False
    try:
        start = time.time()
        while time.time() - start < timeout:
            wins = gw.getWindowsWithTitle(title_pattern)
            if wins:
                win = wins[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.3)
                return True
            time.sleep(0.2)
    except Exception as e:
        print(f"[AUTO] Window activation error: {e}")
    return False

def _find_window(title_pattern: str) -> Optional[object]:
    if not PYGETWINDOW:
        return None
    try:
        wins = gw.getWindowsWithTitle(title_pattern)
        if wins:
            return wins[0]
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
# APP REGISTRY
# ══════════════════════════════════════════════════════════════════════════════
_APPS: dict[str, str | list] = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "notepad": "notepad.exe",
    "wordpad": "wordpad.exe",
    "paint": "mspaint.exe",
    "calculator": "calc.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "explorer": "explorer.exe",
    "settings": "ms-settings:",
    "vscode": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe")],
    "spotify": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe")],
    "whatsapp": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\WhatsApp\WhatsApp.exe")],
    "telegram": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Telegram Desktop\Telegram.exe")],
    "discord": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Discord\Discord.exe")],
    "zoom": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Zoom\bin\Zoom.exe")],
    "teams": [os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Microsoft\Teams\current\Teams.exe")],
}

_WEB_FALLBACKS = {
    "youtube": "https://youtube.com",
    "netflix": "https://netflix.com",
    "amazon": "https://amazon.in",
    "flipkart": "https://flipkart.com",
    "gmail": "https://gmail.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "chatgpt": "https://chat.openai.com",
    "github": "https://github.com",
    "linkedin": "https://linkedin.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "twitter": "https://twitter.com",
    "reddit": "https://reddit.com",
    "wikipedia": "https://wikipedia.org",
}

def _resolve_path(raw: str | list) -> Optional[str]:
    paths = raw if isinstance(raw, list) else [raw]
    for p in paths:
        p = os.path.expandvars(p)
        if os.path.exists(p):
            return p
        if not os.sep in p and not p.startswith("ms-"):
            return p
    return None

# ══════════════════════════════════════════════════════════════════════════════
# OPEN APP
# ══════════════════════════════════════════════════════════════════════════════
def _open_app(name: str) -> Tuple[bool, str]:
    nl = name.lower().strip()
    if nl in _WEB_FALLBACKS:
        url = _WEB_FALLBACKS[nl]
        return _open_in_chrome(url)
    entry = _APPS.get(nl)
    if entry:
        path = _resolve_path(entry)
        if path:
            try:
                if path.startswith("ms-"):
                    os.startfile(path)
                else:
                    subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE if path.endswith("cmd.exe") else 0)
                return True, f"{name.title()} khul gaya, Sir!"
            except Exception as e:
                return False, f"Error: {e}"
    for key, entry in _APPS.items():
        if nl in key or key in nl:
            path = _resolve_path(entry)
            if path:
                try:
                    subprocess.Popen([path])
                    return True, f"{key.title()} khul gaya, Sir!"
                except Exception as e:
                    return False, f"Error opening {key}: {e}"
    url = f"https://www.google.com/search?q={name.replace(' ', '+')}"
    return _open_in_chrome(url)

def _open_in_chrome(url: str) -> Tuple[bool, str]:
    if _CHROME_PATH and os.path.exists(_CHROME_PATH):
        try:
            subprocess.Popen([_CHROME_PATH, url])
            return True, f"Chrome mein khul gaya: {url}"
        except Exception as e:
            print(f"[AUTO] Chrome open error: {e}")
    webbrowser.open(url)
    return True, f"Browser mein khul gaya: {url}"

# ══════════════════════════════════════════════════════════════════════════════
# WEB ACTIONS
# ══════════════════════════════════════════════════════════════════════════════
def _search_web(query: str) -> Tuple[bool, str]:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return _open_in_chrome(url)

def _search_youtube(query: str) -> Tuple[bool, str]:
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    return _open_in_chrome(url)

def _open_url(url: str) -> Tuple[bool, str]:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return _open_in_chrome(url)

def _play_music(query: str) -> Tuple[bool, str]:
    spotify_uri = f"spotify:search:{query.replace(' ', '%20')}"
    try:
        os.startfile(spotify_uri)
        return True, f"Spotify pe '{query}' play ho raha hai, Sir!"
    except Exception:
        pass
    return _search_youtube(f"{query} song")

# ══════════════════════════════════════════════════════════════════════════════
# BROWSER AUTOMATION (V9 NEW)
# ══════════════════════════════════════════════════════════════════════════════
def _open_browser(url: str = "") -> Tuple[bool, str]:
    try:
        if url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            return _open_in_chrome(url)
        else:
            return _open_in_chrome("https://google.com")
    except Exception as e:
        return False, f"Browser error: {e}"

def _fill_form_field(field_label: str, text: str) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        from vision.screen_vision import get_screen_reader
        reader = get_screen_reader({})
        success = reader.find_and_click(field_label)
        if success[0]:
            time.sleep(0.3)
            pyautogui.write(text, interval=0.01)
            return True, f"Filled '{field_label}' with '{text[:30]}...'"
        return False, f"Could not find field '{field_label}'"
    except Exception as e:
        return False, f"Form fill error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# TYPE TEXT
# ══════════════════════════════════════════════════════════════════════════════
def _type_text(text: str, target_app: str = "") -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        if target_app:
            activated = _activate_window(target_app, timeout=3.0)
            if not activated:
                for pattern in [target_app, target_app.title(), target_app.lower(), target_app.upper()]:
                    if _activate_window(pattern, timeout=1.0):
                        activated = True
                        break
            if not activated:
                print(f"[AUTO] Warning: Could not activate '{target_app}'")
            time.sleep(0.5)
        pyautogui.write(text, interval=0.01)
        return True, f"Text type kar diya: '{text[:50]}{'...' if len(text) > 50 else ''}'"
    except Exception as e:
        return False, f"Type error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# SAVE FILE
# ══════════════════════════════════════════════════════════════════════════════
def _save_file(target_app: str = "") -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        if target_app:
            _activate_window(target_app, timeout=2.0)
            time.sleep(0.3)
        pyautogui.hotkey("ctrl", "s")
        return True, "Save dialog khul gaya, Sir!"
    except Exception as e:
        return False, f"Save error: {e}"

def _save_as(target_app: str = "") -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        if target_app:
            _activate_window(target_app, timeout=2.0)
            time.sleep(0.3)
        pyautogui.hotkey("ctrl", "shift", "s")
        return True, "Save As dialog khul gaya, Sir!"
    except Exception as e:
        return False, f"Save As error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# MOUSE CONTROL (V9 ENHANCED)
# ══════════════════════════════════════════════════════════════════════════════
def _mouse_move(x: int, y: int) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        pyautogui.moveTo(x, y, duration=0.5)
        return True, f"Mouse ({x}, {y}) pe gayi"
    except Exception as e:
        return False, f"Mouse move error: {e}"

def _mouse_click(x: Optional[int] = None, y: Optional[int] = None,
                 button: str = "left") -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
            return True, f"Mouse click ({x}, {y}) {button} button"
        else:
            pyautogui.click(button=button)
            return True, f"Mouse click {button} button"
    except Exception as e:
        return False, f"Click error: {e}"

def _double_click(x: Optional[int] = None, y: Optional[int] = None) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
            return True, f"Double-click at ({x}, {y})"
        else:
            pyautogui.doubleClick()
            return True, "Double-click at current position"
    except Exception as e:
        return False, f"Double-click error: {e}"

def _right_click(x: Optional[int] = None, y: Optional[int] = None) -> Tuple[bool, str]:
    return _mouse_click(x, y, button="right")

def _drag_to(x: int, y: int, duration: float = 0.5) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        pyautogui.dragTo(x, y, duration=duration)
        return True, f"Dragged to ({x}, {y})"
    except Exception as e:
        return False, f"Drag error: {e}"

def _drag_rel(x: int, y: int, duration: float = 0.5) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        pyautogui.dragRel(x, y, duration=duration)
        return True, f"Dragged relative ({x}, {y})"
    except Exception as e:
        return False, f"Drag relative error: {e}"

def _scroll_horizontal(clicks: int) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        pyautogui.hscroll(clicks)
        direction = "right" if clicks > 0 else "left"
        return True, f"Horizontal scroll {direction}"
    except Exception as e:
        return False, f"H-scroll error: {e}"

def _mouse_scroll(clicks: int) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        pyautogui.scroll(clicks)
        direction = "up" if clicks > 0 else "down"
        return True, f"Mouse scroll {direction}"
    except Exception as e:
        return False, f"Scroll error: {e}"

def _mouse_position() -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        x, y = pyautogui.position()
        return True, f"Mouse position: ({x}, {y})"
    except Exception as e:
        return False, f"Position error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARD / SCREEN ACTIONS
# ══════════════════════════════════════════════════════════════════════════════
def _hotkey(keys: str) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        parts = [k.strip() for k in keys.replace("+", " ").split()]
        pyautogui.hotkey(*parts)
        return True, f"Hotkey '{keys}' press hua"
    except Exception as e:
        return False, f"Hotkey error: {e}"

def _screenshot() -> Tuple[bool, str]:
    if not PIL:
        if PYAUTOGUI:
            pyautogui.hotkey("win", "printscreen")
            return True, "Screenshot le liya — Pictures/Screenshots mein milega"
        return False, "PIL not installed"
    shots_dir = BASE / "data" / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    fname = shots_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        img = ImageGrab.grab()
        img.save(str(fname))
        return True, f"Screenshot save hua: {fname.name}"
    except Exception as e:
        return False, f"Screenshot error: {e}"

def _read_screen() -> Tuple[bool, str]:
    if not PIL:
        return False, "PIL not installed"
    try:
        from vision.screen_vision import get_screen_reader
        reader = get_screen_reader({})
        text = reader.read(use_ai=False)
        return True, text[:800] if text else "Screen pe koi readable text nahi mila"
    except Exception as e:
        if TESSERACT:
            try:
                img = ImageGrab.grab()
                text = pytesseract.image_to_string(img, lang="eng+hin")
                return True, text[:800].strip() if text else "Screen pe koi text nahi mila"
            except Exception as e2:
                return False, f"Screen read error: {e2}"
        return False, f"Screen read error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# VOLUME & SYSTEM CONTROLS
# ══════════════════════════════════════════════════════════════════════════════
def _volume_up() -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    for _ in range(5):
        pyautogui.press("volumeup")
    return True, "Volume badh gaya, Sir!"

def _volume_down() -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    for _ in range(5):
        pyautogui.press("volumedown")
    return True, "Volume kam ho gaya, Sir!"

def _mute() -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    pyautogui.press("volumemute")
    return True, "Mute ho gaya, Sir!"

def _lock_screen() -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    pyautogui.hotkey("win", "l")
    return True, "Screen lock ho gayi, Sir!"

def _shutdown() -> Tuple[bool, str]:
    return False, "Shutdown cancelled — yeh dangerous command hai, Sir. Aap manually karein."

# ══════════════════════════════════════════════════════════════════════════════
# WINDOW MANAGEMENT (V9 ENHANCED)
# ══════════════════════════════════════════════════════════════════════════════
def _minimize_app(name: str) -> Tuple[bool, str]:
    if not PYGETWINDOW:
        if PYAUTOGUI:
            pyautogui.hotkey("win", "down")
            return True, "Window minimize ho gayi"
        return False, "pygetwindow not installed"
    wins = gw.getWindowsWithTitle(name)
    if wins:
        wins[0].minimize()
        return True, f"'{name}' minimize ho gaya, Sir!"
    return False, f"'{name}' window nahi mili"

def _maximize_app(name: str) -> Tuple[bool, str]:
    if not PYGETWINDOW:
        if PYAUTOGUI:
            pyautogui.hotkey("win", "up")
            return True, "Window maximize ho gayi"
        return False, "pygetwindow not installed"
    wins = gw.getWindowsWithTitle(name)
    if wins:
        wins[0].maximize()
        return True, f"'{name}' maximize ho gaya, Sir!"
    return False, f"'{name}' window nahi mili"

def _close_app(name: str) -> Tuple[bool, str]:
    nl = name.lower().strip()
    if PYGETWINDOW:
        wins = gw.getWindowsWithTitle(nl)
        if wins:
            wins[0].close()
            return True, f"'{name}' band kar diya, Sir!"
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", f"{nl}.exe"],
            capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"'{name}' band ho gaya, Sir!"
    except Exception:
        pass
    return False, f"'{name}' nahi mila band karne ke liye"

def _focus_window(title_pattern: str) -> Tuple[bool, str]:
    if not PYGETWINDOW:
        return False, "pygetwindow not installed"
    try:
        wins = gw.getWindowsWithTitle(title_pattern)
        if wins:
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            return True, f"Window '{title_pattern}' focused"
        return False, f"Window '{title_pattern}' not found"
    except Exception as e:
        return False, f"Focus error: {e}"

def _list_windows() -> Tuple[bool, str]:
    if not PYGETWINDOW:
        return False, "pygetwindow not installed"
    try:
        wins = gw.getAllWindows()
        visible = [w.title for w in wins if w.title and w.visible]
        return True, "Active windows:\n" + "\n".join(f"  • {t}" for t in visible[:20])
    except Exception as e:
        return False, f"List windows error: {e}"

def _resize_window(title_pattern: str, width: int, height: int) -> Tuple[bool, str]:
    if not PYGETWINDOW:
        return False, "pygetwindow not installed"
    try:
        wins = gw.getWindowsWithTitle(title_pattern)
        if wins:
            wins[0].resizeTo(width, height)
            return True, f"Resized '{title_pattern}' to {width}x{height}"
        return False, f"Window '{title_pattern}' not found"
    except Exception as e:
        return False, f"Resize error: {e}"

def _move_window(title_pattern: str, x: int, y: int) -> Tuple[bool, str]:
    if not PYGETWINDOW:
        return False, "pygetwindow not installed"
    try:
        wins = gw.getWindowsWithTitle(title_pattern)
        if wins:
            wins[0].moveTo(x, y)
            return True, f"Moved '{title_pattern}' to ({x}, {y})"
        return False, f"Window '{title_pattern}' not found"
    except Exception as e:
        return False, f"Move error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM INFO (V9 NEW)
# ══════════════════════════════════════════════════════════════════════════════
def _system_info() -> Tuple[bool, str]:
    if not PSUTIL:
        return False, "psutil not installed — run: pip install psutil"
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        info = (
            f"CPU: {cpu}%\n"
            f"RAM: {mem.percent}% used ({mem.used//(1024**3)}GB / {mem.total//(1024**3)}GB)\n"
            f"Disk: {disk.percent}% used ({disk.used//(1024**3)}GB / {disk.total//(1024**3)}GB)\n"
            f"Boot: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M')}"
        )
        return True, info
    except Exception as e:
        return False, f"System info error: {e}"

def _list_processes(name_filter: str = "") -> Tuple[bool, str]:
    if not PSUTIL:
        return False, "psutil not installed"
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                n = p.info['name']
                if not name_filter or name_filter.lower() in n.lower():
                    procs.append(f"  PID {p.info['pid']:>6}: {n} ({p.info['cpu_percent']}%)")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return True, f"Processes{' matching '+name_filter if name_filter else ''}:\n" + "\n".join(procs[:30])
    except Exception as e:
        return False, f"Process list error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# CLICK TEXT (OCR-based)
# ══════════════════════════════════════════════════════════════════════════════
def _click_text(target: str) -> Tuple[bool, str]:
    if not PYAUTOGUI:
        return False, "pyautogui not installed"
    try:
        loc = pyautogui.locateOnScreen(target, confidence=0.8)
        if loc:
            pyautogui.click(loc)
            return True, f"'{target}' click ho gaya"
    except Exception:
        pass
    # Fallback: try OCR-based click via vision module
    try:
        from vision.screen_vision import get_screen_reader
        reader = get_screen_reader({})
        result = reader.find_and_click(target)
        if result[0]:
            return True, f"'{target}' click ho gaya (OCR-based)"
    except Exception:
        pass
    return False, f"'{target}' screen pe nahi mila"

def _find_and_click(target: str) -> Tuple[bool, str]:
    return _click_text(target)

# ══════════════════════════════════════════════════════════════════════════════
# SAFETY CHECK
# ══════════════════════════════════════════════════════════════════════════════
_DESTRUCTIVE_ACTIONS = {"shutdown", "delete_file", "format", "rm", "del"}

def _is_safe(action: str) -> Tuple[bool, str]:
    if action.lower() in _DESTRUCTIVE_ACTIONS:
        return False, f"Action '{action}' is destructive and requires manual confirmation."
    return True, "OK"

# ══════════════════════════════════════════════════════════════════════════════
# CENTRAL EXECUTOR
# ══════════════════════════════════════════════════════════════════════════════
class Automation:
    def __init__(self, settings: dict = None):
        self.settings = settings or {}
        self.safety_enabled = self.settings.get("V9_NEW", {}).get("safety_confirm_destructive", True)

    def execute(self, action: dict) -> Tuple[bool, str]:
        act = (action.get("action") or "").strip().lower()
        target = (action.get("target") or "").strip()
        print(f"[AUTO] {act!r} → target={target!r}")

        # Safety check
        if self.safety_enabled:
            safe, msg = _is_safe(act)
            if not safe:
                return False, msg

        dispatch = {
            # Apps
            "open_app": lambda: _open_app(target),
            "close_app": lambda: _close_app(target),

            # Web
            "search_web": lambda: _search_web(target),
            "search_youtube": lambda: _search_youtube(target),
            "play_music": lambda: _play_music(target),
            "open_url": lambda: _open_url(target),
            "open_browser": lambda: _open_browser(target),
            "fill_form": lambda: _fill_form_field(
                target.split("|")[0] if "|" in target else target,
                target.split("|")[1] if "|" in target else ""),

            # Mouse
            "mouse_move": lambda: _mouse_move(
                int(target.split(',')[0]) if ',' in target else 500,
                int(target.split(',')[1]) if ',' in target else 500),
            "mouse_click": lambda: _mouse_click(),
            "double_click": lambda: _double_click(
                int(target.split(',')[0]) if ',' in target else None,
                int(target.split(',')[1]) if ',' in target else None),
            "right_click": lambda: _right_click(
                int(target.split(',')[0]) if ',' in target else None,
                int(target.split(',')[1]) if ',' in target else None),
            "drag_to": lambda: _drag_to(
                int(target.split(',')[0]),
                int(target.split(',')[1]) if ',' in target else 500),
            "drag_rel": lambda: _drag_rel(
                int(target.split(',')[0]),
                int(target.split(',')[1]) if ',' in target else 0),
            "scroll_left": lambda: _scroll_horizontal(-5),
            "scroll_right": lambda: _scroll_horizontal(5),
            "mouse_scroll_up": lambda: _mouse_scroll(5),
            "mouse_scroll_down": lambda: _mouse_scroll(-5),
            "mouse_position": lambda: _mouse_position(),

            # Keyboard/Screen
            "screenshot": lambda: _screenshot(),
            "read_screen": lambda: _read_screen(),
            "type_text": lambda: _type_text(target, action.get("app", "")),
            "hotkey": lambda: _hotkey(target),
            "click_text": lambda: _click_text(target),
            "find_and_click": lambda: _find_and_click(target),
            "scroll_down": lambda: _mouse_scroll(-3),
            "scroll_up": lambda: _mouse_scroll(3),

            # Save
            "save_file": lambda: _save_file(action.get("app", "")),
            "save_as": lambda: _save_as(action.get("app", "")),

            # Volume/System
            "volume_up": lambda: _volume_up(),
            "volume_down": lambda: _volume_down(),
            "mute": lambda: _mute(),
            "lock_screen": lambda: _lock_screen(),
            "shutdown": lambda: _shutdown(),
            "system_info": lambda: _system_info(),
            "list_processes": lambda: _list_processes(target),

            # Window
            "minimize_app": lambda: _minimize_app(target),
            "maximize_app": lambda: _maximize_app(target),
            "focus_window": lambda: _focus_window(target),
            "list_windows": lambda: _list_windows(),
            "resize_window": lambda: _resize_window(
                target.split(',')[0],
                int(target.split(',')[1]) if ',' in target else 800,
                int(target.split(',')[2]) if target.count(',') >= 2 else 600),
            "move_window": lambda: _move_window(
                target.split(',')[0],
                int(target.split(',')[1]) if ',' in target else 0,
                int(target.split(',')[2]) if target.count(',') >= 2 else 0),
        }

        fn = dispatch.get(act)
        if fn:
            try:
                return fn()
            except Exception as e:
                return False, f"Action '{act}' mein error aaya: {e}"

        return False, f"Unknown action: '{act}'"

    def execute_all(self, actions: list) -> list[Tuple[bool, str]]:
        results = []
        for a in actions:
            ok, msg = self.execute(a)
            results.append((ok, msg))
            if not ok:
                print(f"[AUTO] ✗ {msg}")
            else:
                print(f"[AUTO] ✓ {msg}")
            time.sleep(0.15)
        return results
