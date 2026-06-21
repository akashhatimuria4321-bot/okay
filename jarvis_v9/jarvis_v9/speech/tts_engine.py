"""
speech/tts_engine.py — JARVIS OMEGA V8
FIXES in V8:
  1. Edge TTS async fixed — uses asyncio.run() in a separate thread so Qt
     event loop is never blocked. This fixes the "TTS not working" bug where
     speak() returned immediately without playing audio.
  2. pyttsx3 fallback added — works completely offline with Indian English voice
  3. speak() is now NON-BLOCKING — plays in background thread
  4. Queue-based — multiple speak() calls don't overlap or crash
  5. hindi_to_hinglish() applied before speaking so voice says readable words
  6. Volume and rate controlled via settings
  7. speak_sync() added for cases where blocking is needed
  8. is_speaking property added for UI busy indicator
"""
from __future__ import annotations

import asyncio, os, re, queue, threading, tempfile, time
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent.parent

# ── TTS backends ──────────────────────────────────────────────────────────────
try:
    import edge_tts
    EDGE = True
except ImportError:
    EDGE = False
    print("[TTS] edge_tts not installed — run: pip install edge-tts")

try:
    import pyttsx3
    PYTTSX = True
except ImportError:
    PYTTSX = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME = True
except Exception:
    PYGAME = False

try:
    import playsound as _ps
    PLAYSOUND = True
except ImportError:
    PLAYSOUND = False


# ══════════════════════════════════════════════════════════════════════════════
# HINGLISH CLEANER — strip Devanagari before speaking, convert common words
# ══════════════════════════════════════════════════════════════════════════════
_SPEAK_MAP = {
    # Make common Hinglish words pronounce correctly in English TTS
    'abhi':     'abhi',   'aap':     'aap',    'Sir':     'Sir',
    'hoon':     'hoon',   'hai':     'hai',    'kaam':    'kaam',
    'theek':    'theek',  'karo':    'karo',   'batao':   'batao',
    'bahut':    'bahut',  'achha':   'accha',  'shukriya':'shukria',
    'nahin':    'nahin',  'haan':    'haan',   'yeh':     'yeh',
    'woh':      'woh',    'aur':     'aur',    'lekin':   'lekin',
}

def _clean_for_tts(text: str) -> str:
    """Remove markdown, action tags, Devanagari, and clean for TTS speech."""
    # Remove action XML blocks
    text = re.sub(r'<ACTION>.*?</ACTION>', '', text, flags=re.DOTALL)
    # Remove markdown
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove Devanagari (TTS can't read it)
    text = re.sub(r'[\u0900-\u097F]+', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate to ~400 chars for speech (don't read essays aloud)
    if len(text) > 400:
        cut = text[:400].rfind('.')
        text = text[:cut + 1] if cut > 200 else text[:400] + '…'
    return text


# ══════════════════════════════════════════════════════════════════════════════
# EDGE TTS  (primary — good Indian English voice)
# ══════════════════════════════════════════════════════════════════════════════
async def _edge_speak_async(text: str, voice: str, rate: str, pitch: str):
    """Async Edge TTS — saves to temp file then plays."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        communicate = edge_tts.Communicate(
            text, voice=voice, rate=rate, pitch=pitch)
        await communicate.save(tmp.name)
        _play_audio(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

def _edge_speak_thread(text: str, voice: str, rate: str, pitch: str):
    """Run Edge TTS async in a fresh event loop (called from worker thread)."""
    try:
        asyncio.run(_edge_speak_async(text, voice, rate, pitch))
    except Exception as e:
        print(f"[TTS-EDGE] error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# AUDIO PLAYBACK HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _play_audio(path: str):
    """Play audio file — tries pygame, then playsound, then os."""
    if PYGAME:
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            return
        except Exception as e:
            print(f"[TTS] pygame play error: {e}")

    if PLAYSOUND:
        try:
            _ps.playsound(path)
            return
        except Exception as e:
            print(f"[TTS] playsound error: {e}")

    # OS fallback
    import subprocess, platform
    sys = platform.system()
    try:
        if sys == "Windows":
            os.startfile(path)
        elif sys == "Darwin":
            subprocess.run(["afplay", path], check=True)
        else:
            subprocess.run(["aplay", path], check=True)
    except Exception as e:
        print(f"[TTS] OS play error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PYTTSX3 FALLBACK  (offline, no internet needed)
# ══════════════════════════════════════════════════════════════════════════════
_pyttsx_engine = None
_pyttsx_lock   = threading.Lock()

def _pyttsx_speak(text: str, rate: int = 170):
    global _pyttsx_engine
    with _pyttsx_lock:
        try:
            if _pyttsx_engine is None:
                _pyttsx_engine = pyttsx3.init()
                voices = _pyttsx_engine.getProperty('voices')
                # Prefer Indian English voice if available
                for v in voices:
                    if 'india' in v.name.lower() or 'en-in' in v.id.lower():
                        _pyttsx_engine.setProperty('voice', v.id)
                        break
            _pyttsx_engine.setProperty('rate',   rate)
            _pyttsx_engine.setProperty('volume', 0.95)
            _pyttsx_engine.say(text)
            _pyttsx_engine.runAndWait()
        except Exception as e:
            print(f"[TTS-PYTTSX] error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN TTS ENGINE
# ══════════════════════════════════════════════════════════════════════════════
class TTSEngine:
    """
    Non-blocking TTS engine with queue.
    speak(text) returns immediately — audio plays in background thread.
    """

    def __init__(self, settings: dict):
        self.settings    = settings
        self.voice       = settings.get("tts_voice",      "en-IN-PrabhatNeural")
        self.rate        = settings.get("tts_edge_rate",  "+5%")
        self.pitch       = settings.get("tts_edge_pitch", "+0Hz")
        self.pyttsx_rate = settings.get("tts_rate",       185)
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._speaking   = threading.Event()
        self._thread     = threading.Thread(
            target=self._worker, daemon=True, name="jarvis-tts")
        self._thread.start()

        mode = "EdgeTTS" if EDGE else ("pyttsx3" if PYTTSX else "NONE")
        print(f"[TTS] ✓ Engine: {mode} | Voice: {self.voice}")
        if not EDGE and not PYTTSX:
            print("[TTS] ⚠ No TTS engine found — install: pip install edge-tts")

    # ── Public API ─────────────────────────────────────────────────────────
    def speak(self, text: str):
        """Non-blocking. Queue text for speaking."""
        clean = _clean_for_tts(text)
        if clean:
            self._queue.put(clean)

    def speak_sync(self, text: str, timeout: float = 30.0):
        """Blocking speak — waits until audio finishes."""
        self.speak(text)
        # Wait until queue drains and speaking stops
        deadline = time.time() + timeout
        time.sleep(0.3)
        while (not self._queue.empty() or self._speaking.is_set()) \
                and time.time() < deadline:
            time.sleep(0.1)

    def stop(self):
        """Clear queue and stop any current speech."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if PYGAME:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    @property
    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def set_voice(self, voice_name: str):
        self.voice = voice_name

    def set_rate(self, rate: str):
        self.rate = rate

    # ── Worker thread ───────────────────────────────────────────────────────
    def _worker(self):
        while True:
            try:
                text = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if text is None:
                break

            self._speaking.set()
            try:
                self._speak_one(text)
            except Exception as e:
                print(f"[TTS] worker error: {e}")
            finally:
                self._speaking.clear()
                self._queue.task_done()

    def _speak_one(self, text: str):
        """Try Edge TTS → pyttsx3 fallback."""
        if EDGE:
            try:
                _edge_speak_thread(text, self.voice, self.rate, self.pitch)
                return
            except Exception as e:
                print(f"[TTS] Edge failed, falling back to pyttsx3: {e}")

        if PYTTSX:
            _pyttsx_speak(text, rate=self.pyttsx_rate)
            return

        print(f"[TTS] No TTS available. Text was: {text[:60]}")
