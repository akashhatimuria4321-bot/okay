"""
main.py — JARVIS OMEGA V9
Entry point. Loads settings, validates API keys, starts Qt app.
Supports both Full GUI mode and ESC Orb mode.
Python 3.14.5
"""
from __future__ import annotations
import sys, os, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# ── Load .env ────────────────────────────────────────────────────────────────
def _load_env():
    env_file = BASE / ".env"
    if not env_file.exists():
        print("[MAIN] .env not found — copy .env.example to .env and add your keys")
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ[k] = v

_load_env()

# ── API Key Validators ───────────────────────────────────────────────────────
def _validate_keys(settings: dict) -> list[str]:
    warnings = []
    groq = settings.get("groq_api_key", "")
    if groq and not groq.startswith("gsk_"):
        warnings.append("GROQ key format wrong — should start with 'gsk_'")
    elif not groq:
        warnings.append("GROQ key missing — Whisper STT won't work")

    cerebras = settings.get("cerebras_api_key", "")
    if cerebras and not cerebras.startswith("csk-"):
        warnings.append("CEREBRAS key format wrong")

    sambanova = settings.get("sambanova_api_key", "")
    if sambanova:
        uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pat, sambanova, re.I):
            warnings.append("SAMBANOVA key format wrong — should be UUID")

    openrouter = settings.get("openrouter_api_key", "")
    if openrouter:
        uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pat, openrouter, re.I):
            warnings.append("OPENROUTER key format wrong — should be UUID")

    nvidia = settings.get("nvidia_api_key", "")
    if nvidia and not nvidia.startswith("nvapi-"):
        warnings.append("NVIDIA key format wrong")

    google = settings.get("google_api_key", "")
    if google and not google.startswith("AIza"):
        warnings.append("GOOGLE key format wrong")

    return warnings

# ── Load Settings ─────────────────────────────────────────────────────────────
def _load_settings() -> dict:
    path = BASE / "config" / "settings.json"
    try:
        s: dict = json.loads(path.read_text(encoding="utf-8"))
        s.pop("_comment", None)
        s.pop("_key_info", None)
    except FileNotFoundError:
        print("[MAIN] settings.json not found, using defaults")
        s = {}
    except json.JSONDecodeError as e:
        print(f"[MAIN] settings.json parse error: {e}")
        s = {}

    key_map = {
        "GROQ_API_KEY": "groq_api_key",
        "CEREBRAS_API_KEY": "cerebras_api_key",
        "SAMBANOVA_API_KEY": "sambanova_api_key",
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "NVIDIA_API_KEY": "nvidia_api_key",
        "GOOGLE_API_KEY": "google_api_key",
        "OPENAI_API_KEY": "openai_api_key",
        "OLLAMA_URL": "ollama_url",
        "OLLAMA_MODEL": "ollama_model",
    }
    for env_var, setting_key in key_map.items():
        val = os.getenv(env_var, "").strip()
        if val:
            s[setting_key] = val

    s.setdefault("user_name", "Sir")
    s.setdefault("ai_name", "JARVIS")
    s.setdefault("tts_voice", "en-IN-PrabhatNeural")
    s.setdefault("tts_edge_rate", "+5%")
    s.setdefault("tts_edge_pitch", "+0Hz")
    s.setdefault("tts_rate", 185)
    s.setdefault("hinglish_display_mode", True)
    s.setdefault("hinglish_speak_mode", True)
    s.setdefault("hindi_speak_mode", False)
    s.setdefault("stt_language", "hi-en")
    s.setdefault("stt_fallback_langs", ["hi-IN", "en-IN", "en-US"])
    s.setdefault("whisper_model", "base")
    s.setdefault("offline_mode", False)
    s.setdefault("ollama_url", "http://localhost:11434")
    s.setdefault("ollama_model", "llama3.2")
    s.setdefault("ollama_vision_model", "llava")
    s.setdefault("theme", "dark_blue")

    # V9 defaults
    s.setdefault("V9_NEW", {})
    s["V9_NEW"].setdefault("esc_orb_mode", False)
    s["V9_NEW"].setdefault("esc_orb_size", 120)
    s["V9_NEW"].setdefault("computer_control_enabled", True)
    s["V9_NEW"].setdefault("vision_enabled", True)
    s["V9_NEW"].setdefault("learning_enabled", True)

    return s

# ── Qt High-DPI ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

# ── Start ─────────────────────────────────────────────────────────────────────
def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS OMEGA V9")
    app.setQuitOnLastWindowClosed(False)

    settings = _load_settings()

    key_names = ["groq", "cerebras", "sambanova", "openrouter", "nvidia", "google", "openai"]
    found = [n for n in key_names if settings.get(f"{n}_api_key", "")]
    missing = [n for n in key_names if not settings.get(f"{n}_api_key", "")]
    print(f"[MAIN] ✓ Keys loaded: {found}")
    if missing:
        print(f"[MAIN] ✗ Keys missing: {missing}")

    warnings = _validate_keys(settings)
    for w in warnings:
        print(f"[MAIN] ⚠ KEY WARNING: {w}")

    if settings.get("offline_mode"):
        print(f"[MAIN] 🔌 Offline mode ON — using Ollama at {settings['ollama_url']}")
    else:
        print("[MAIN] 🌐 Online mode — will use cloud APIs")

    # V9: Choose between Full GUI or ESC Orb mode
    orb_mode = settings.get("V9_NEW", {}).get("esc_orb_mode", False)

    if orb_mode:
        print("[MAIN] 🎯 ESC Orb Mode — Floating transparent assistant")
        from gui.orb_window import OrbMainWindow
        win = OrbMainWindow(settings)
    else:
        print("[MAIN] 🖥️  Full GUI Mode — Starfield + Arc Reactor")
        from gui.main_window import JarvisOmegaWindow
        win = JarvisOmegaWindow(settings)
        win.show()

    print("[MAIN] JARVIS OMEGA V9 started — press SPACE to speak, ESC to minimise/orb toggle")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
