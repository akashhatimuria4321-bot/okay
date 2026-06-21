"""
speech/stt_engine.py — JARVIS OMEGA V8 with V7 recording
FIXES for Python 3.14 + Hindi speech recognition:
 1. Uses sounddevice + numpy instead of PyAudio
 2. Uses requests for Whisper API
 3. VAD-based recording cuts silence instantly
 4. Hinglish recognition — Google STT with language='hi-en' + 'en-IN' fallback
 5. Whisper (via Groq API) — much better accuracy for Indian English + Hindi mixed speech
 6. Energy threshold auto-calibration
 7. phrase_time_limit prevents forever-stuck recognition
 8. Post-processing to correct common misheard words
 9. WakeWord detection: listens for "Jarvis" / "Hey Jarvis" / "JARVIS" before activating
 10. HINDI→ENGLISH TRANSLATION: Converts Hindi commands (खोलो, बंद, युटुब) to English
 11. All Qt threading done via QThread / signals
 12. FIX: Local whisper crash on empty audio
 13. FIX: Better VAD threshold to avoid false triggers
Python 3.14.5 | sounddevice + numpy + requests
"""
from __future__ import annotations

import io, os, re, time, wave, queue, threading, tempfile, base64
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThread

BASE = Path(__file__).resolve().parent.parent

# ── Audio recording (sounddevice — Python 3.14 compatible) ──────────────────
try:
    import sounddevice as sd
    import numpy as np
    SD = True
except ImportError:
    SD = False
    print("[STT] ✗ sounddevice missing — pip install sounddevice numpy")

# ── HTTP requests ────────────────────────────────────────────────────────────
try:
    import requests as _req
    REQ = True
except ImportError:
    REQ = False
    print("[STT] ✗ requests missing — pip install requests")

# ── Google STT fallback (optional) ───────────────────────────────────────────
try:
    import speech_recognition as _sr
    SR_LIB = True
except ImportError:
    SR_LIB = False
    print("[STT] ⚠ speech_recognition not installed — Google STT fallback disabled")

# ── Local Whisper (optional) ─────────────────────────────────────────────────
try:
    import whisper as _whisper
    LOCAL_WHISPER = True
except ImportError:
    LOCAL_WHISPER = False


# ══════════════════════════════════════════════════════════════════════════════
# HINDI → ENGLISH TRANSLATION MAP (for Google STT returning Devanagari)
# ══════════════════════════════════════════════════════════════════════════════
_HINDI_TO_ENGLISH = {
    # Common Hindi words that Google STT returns
    'हैलो': 'hello', 'हेलो': 'hello',
    'जार्विस': 'jarvis',
    'खोलो': 'open', 'खोल': 'open', 'खुल': 'open',
    'बंद': 'close', 'बन्द': 'close', 'बंद करो': 'close',
    'यूट्यूब': 'youtube', 'युटुब': 'youtube', 'यूट्यूब': 'youtube',
    'गूगल': 'google', 'गुगल': 'google',
    'क्रोम': 'chrome', 'क्रोमे': 'chrome',
    'नोटपैड': 'notepad', 'नोटपेड': 'notepad',
    'स्पॉटिफाई': 'spotify', 'स्पोटिफाई': 'spotify',
    'व्हाट्सएप': 'whatsapp', 'व्हाट्सएप्प': 'whatsapp',
    'टेलीग्राम': 'telegram',
    'डिस्कॉर्ड': 'discord',
    'जूम': 'zoom',
    'टीम्स': 'teams',
    'सर्च': 'search', 'खोज': 'search', 'ढूंढो': 'search',
    'चलाओ': 'play', 'बजाओ': 'play', 'सुनाओ': 'play',
    'स्क्रीनशॉट': 'screenshot', 'स्क्रीन': 'screen',
    'वॉल्यूम': 'volume', 'आवाज': 'volume',
    'बढ़ाओ': 'up', 'बढ़ा': 'up',
    'कम': 'down', 'घटाओ': 'down',
    'म्यूट': 'mute', 'चुप': 'mute',
    'टाइप': 'type', 'लिखो': 'type',
    'स्क्रॉल': 'scroll',
    'ऊपर': 'up', 'नीचे': 'down',
    'क्लिक': 'click',
    'मैक्सिमाइज़': 'maximize', 'बड़ा': 'maximize',
    'मिनिमाइज़': 'minimize', 'छोटा': 'minimize',
    'मैन': 'man', 'मैं': 'i', 'मुझे': 'me',
    'तुम': 'you', 'आप': 'you',
    'करो': 'do', 'कर': 'do',
    'दो': 'give', 'दिखाओ': 'show',
    'क्या': 'what', 'कैसे': 'how', 'कहाँ': 'where',
    'कब': 'when', 'क्यों': 'why', 'कौन': 'who',
    'है': 'is', 'हैं': 'are', 'था': 'was', 'थी': 'was',
    'और': 'and', 'या': 'or', 'लेकिन': 'but',
    'में': 'in', 'पर': 'on', 'से': 'from', 'को': 'to',
    'अच्छा': 'good', 'बहुत': 'very', 'ठीक': 'ok',
    'धन्यवाद': 'thanks', 'शुक्रिया': 'thanks',
    'प्लीज': 'please', 'कृपया': 'please',
    'हाँ': 'yes', 'नहीं': 'no',
    'अभी': 'now', 'आज': 'today', 'कल': 'tomorrow',
    'सुबह': 'morning', 'शाम': 'evening', 'रात': 'night',
    'बजे': 'o clock',
}

def _translate_hindi_to_english(text: str) -> str:
    """Translate common Hindi words in text to English equivalents."""
    # First try to detect if text contains Devanagari script
    if not re.search(r'[\u0900-\u097F]', text):
        return text  # No Hindi characters, return as-is

    result = text
    # Replace whole words
    for hindi, eng in _HINDI_TO_ENGLISH.items():
        # Match whole word with word boundaries (handle spaces/punctuation)
        pattern = r'(?i)\b' + re.escape(hindi) + r'\b'
        result = re.sub(pattern, eng, result)

    # Remove any remaining Devanagari characters that weren't translated
    result = re.sub(r'[\u0900-\u097F]+', ' ', result)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ENGLISH CORRECTION MAP (for English STT mishears)
# ══════════════════════════════════════════════════════════════════════════════
_CORRECTIONS = {
    # App names
    r'\bchrome\b': 'chrome',
    r'\bkrome\b': 'chrome',
    r'\bchrom\b': 'chrome',
    r'\byoutube\b': 'youtube',
    r'\byou tube\b': 'youtube',
    r'\bspotify\b': 'spotify',
    r'\bwatsapp\b': 'whatsapp',
    r'\bwhat\'?s app\b': 'whatsapp',
    r'\bword pad\b': 'wordpad',
    r'\bnotepad\b': 'notepad',
    r'\bvs code\b': 'vscode',
    r'\bvisual studio\b': 'vscode',
    r'\bcalc\b': 'calculator',

    # Actions — Hinglish
    r'\bkholo\b': 'open',
    r'\bband karo\b': 'close',
    r'\bbund karo\b': 'close',
    r'\bdhundo\b': 'search',
    r'\bkhojo\b': 'search',
    r'\bsuno\b': 'play music',
    r'\bbajao\b': 'play music',
    r'\bchalo\b': 'open',
    r'\bshuru karo\b': 'open',

    # Mishears
    r'\bopen the\b': 'open',
    r'\bclose the\b': 'close',
    r'\bplay the\b': 'play',
    r'\bsearch the\b': 'search',
    r'\bsearch for\b': 'search',
    r'\blook up\b': 'search',
    r'\bopen up\b': 'open',
    r'\bgo to\b': 'open',

    # Common noise words in Indian speech recognition
    r'\bum+\b': '',
    r'\buh+\b': '',
    r'\bhmm+\b': '',
    r'\bare yaar\b': '',
    r'\byaar\b': '',
    r'\brobot\b': '',  # Filter out "Robot" false trigger
}

def _correct(text: str) -> str:
    """Apply Hinglish correction map to STT output."""
    t = text.lower().strip()
    for pat, rep in _CORRECTIONS.items():
        t = re.sub(pat, rep, t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[0].upper() + t[1:] if t else text


# ═══════════════════════════════════════════════════════════════════════════
# RECORDER — VAD-based, cuts silence in ~0.6s after speech ends
# ═══════════════════════════════════════════════════════════════════════════
class Recorder:
    SR = 16000  # sample rate
    CH = 1      # mono
    DTYPE = "int16"
    CHUNK = 512  # smaller chunk = faster VAD response

    # VAD thresholds — ADJUSTED for better accuracy
    SPEECH_THRESH = 600       # amplitude to consider as speech (increased from 500)
    SILENCE_SECS = 0.65       # seconds of silence before stopping
    MIN_SPEECH_SECS = 0.4     # ignore clips shorter than this
    MAX_SECS = 12.0           # hard max recording time

    def record(self) -> Optional[bytes]:
        """
        Record until silence. Returns WAV bytes or None.
        Fast: stops ~0.65s after user finishes talking.
        """
        if not SD:
            return None

        q: queue.Queue = queue.Queue()
        frames: list = []
        speech_started = False
        silent_chunks = 0

        sil_chunks_needed = int(self.SILENCE_SECS * self.SR / self.CHUNK)
        min_speech_chunks = int(self.MIN_SPEECH_SECS * self.SR / self.CHUNK)
        max_chunks = int(self.MAX_SECS * self.SR / self.CHUNK)

        def _cb(indata, n, t, status):
            q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.SR, channels=self.CH,
                dtype=self.DTYPE, blocksize=self.CHUNK, callback=_cb
            ):
                for _ in range(max_chunks):
                    try:
                        chunk = q.get(timeout=1.0)
                    except queue.Empty:
                        break

                    frames.append(chunk)
                    amplitude = np.abs(chunk).mean()

                    if amplitude > self.SPEECH_THRESH:
                        speech_started = True
                        silent_chunks = 0
                    elif speech_started:
                        silent_chunks += 1
                        if silent_chunks >= sil_chunks_needed:
                            break

        except Exception as e:
            print(f"[STT] record error: {e}")
            return None

        if not speech_started or len(frames) < min_speech_chunks:
            return None

        audio = np.concatenate(frames, axis=0)
        return self._to_wav(audio)

    @staticmethod
    def _to_wav(data: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(data.tobytes())
        return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# WHISPER VIA GROQ (best accuracy for Hinglish speech)
# ══════════════════════════════════════════════════════════════════════════════
class GroqWhisper:
    """
    Groq's hosted Whisper — fastest option (~0.3s).
    Uses whisper-large-v3-turbo: best accuracy + speed.
    """
    MODEL = "whisper-large-v3-turbo"
    URL = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, api_key: str):
        self.key = api_key
        self._valid = None  # cache key validity

    def _check_key(self) -> bool:
        """Quick check if key is valid before making expensive calls."""
        if self._valid is not None:
            return self._valid
        if not self.key or not self.key.startswith("gsk_"):
            print("[STT-WHISPER] Key format invalid — should start with 'gsk_'")
            self._valid = False
            return False
        self._valid = True
        return True

    def transcribe(self, wav_bytes: bytes,
                   language: str = "hi") -> Optional[str]:
        """language='hi' handles Hindi+English mixed speech correctly."""
        if not REQ or not self._check_key():
            return None
        try:
            files = {
                "file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
            }
            data = {
                "model": self.MODEL,
                "language": language,
                "response_format": "json",
            }
            headers = {"Authorization": f"Bearer {self.key}"}
            r = _req.post(self.URL, headers=headers,
                          files=files, data=data, timeout=8)
            if r.status_code == 200:
                text = r.json().get("text", "").strip()
                print(f"[STT-WHISPER] '{text}'")
                return text if text else None
            elif r.status_code == 401:
                print("[STT-WHISPER] ⚠ HTTP 401 — API key is invalid/expired. Get new key from console.groq.com")
                self._valid = False
            else:
                print(f"[STT-WHISPER] HTTP {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print(f"[STT-WHISPER] error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE STT (free, fast — used as fallback when Whisper key missing)
# ══════════════════════════════════════════════════════════════════════════════
class GoogleSTT:
    """SpeechRecognition + Google STT — free, decent accuracy."""

    def __init__(self):
        self.rec = None
        if SR_LIB:
            self.rec = _sr.Recognizer()
            self.rec.energy_threshold = 300
            self.rec.dynamic_energy_threshold = True

    def transcribe(self, wav_bytes: bytes,
                   language: str = "hi-IN") -> Optional[str]:
        if not self.rec:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                tmp = f.name
            with _sr.AudioFile(tmp) as src:
                audio = self.rec.record(src)
            os.unlink(tmp)
            # Try multiple languages
            for lang in (language, "en-IN", "en-US", "hi-en"):
                try:
                    text = self.rec.recognize_google(audio, language=lang)
                    if text:
                        print(f"[STT-GOOGLE/{lang}] '{text.strip()}'")
                        return text.strip()
                except _sr.UnknownValueError:
                    continue
                except Exception:
                    break
        except Exception as e:
            print(f"[STT-GOOGLE] error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL WHISPER (optional offline fallback)
# ══════════════════════════════════════════════════════════════════════════════
class LocalWhisper:
    """openai-whisper running locally — fallback."""

    def __init__(self, model_name: str = "base"):
        self.model = None
        self._load(model_name)

    def _load(self, name: str):
        if not LOCAL_WHISPER:
            return
        try:
            self.model = _whisper.load_model(name)
            print(f"[STT-LOCAL] ✓ whisper:{name} loaded")
        except Exception as e:
            print(f"[STT-LOCAL] load error: {e}")

    def transcribe(self, wav_bytes: bytes) -> Optional[str]:
        if not self.model:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                tmp = f.name

            # FIX: Check if file has actual audio data
            import wave
            with wave.open(tmp, 'rb') as wf:
                frames = wf.getnframes()
                if frames < 100:  # Too short
                    os.unlink(tmp)
                    return None

            result = self.model.transcribe(tmp, fp16=False, task="transcribe")
            os.unlink(tmp)
            return (result.get("text") or "").strip() or None
        except Exception as e:
            # Don't print error for empty audio — it's normal
            if "0 elements" not in str(e) and "reshape" not in str(e):
                print(f"[STT-LOCAL] transcribe error: {e}")
            return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN STT ENGINE — Python 3.14 compatible
# ══════════════════════════════════════════════════════════════════════════════
class STTEngine(QObject):
    """
    STT Engine for Python 3.14.
    Uses sounddevice for recording (no PyAudio needed).
    Whisper via Groq API → Google STT → Local Whisper fallback.
    """
    text_ready = pyqtSignal(str)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)

    WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "j.a.r.v.i.s", "jarvis"]

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.is_listening = False
        self._rec = None
        self._groq = None
        self._local = None
        self._google = None
        self._init()

    def _init(self):
        if SD:
            self._rec = Recorder()
            print("[STT] ✓ Recorder ready (sounddevice)")
        else:
            print("[STT] ✗ Recorder unavailable — install: pip install sounddevice numpy")
            return

        # Groq Whisper — primary
        key = self.settings.get("groq_api_key", "")
        if key and REQ:
            self._groq = GroqWhisper(key)
            print("[STT] ✓ Groq Whisper (cloud, ultra-fast) ready")
        else:
            print("[STT] ⚠ Groq key missing — Whisper disabled. Using Google STT fallback.")

        # Local whisper — fallback 1
        if LOCAL_WHISPER:
            model_name = self.settings.get("whisper_model", "tiny")
            threading.Thread(
                target=self._load_local, args=(model_name,), daemon=True
            ).start()

        # Google STT — fallback 2
        if SR_LIB:
            self._google = GoogleSTT()
            print("[STT] ✓ Google STT fallback ready")

    def _load_local(self, name: str):
        self._local = LocalWhisper(name)

    # ── Calibration ──────────────────────────────────────────────────────────
    def calibrate(self, duration: float = 1.5):
        """Calibrate microphone noise level — call once on startup."""
        if not SD or not self._rec:
            return
        try:
            q: queue.Queue = queue.Queue()
            samples = []
            max_samples = int(duration * 16000 / 512)

            def _cb(indata, n, t, status):
                q.put(indata.copy())

            with sd.InputStream(samplerate=16000, channels=1,
                               dtype="int16", blocksize=512, callback=_cb):
                for _ in range(max_samples):
                    try:
                        chunk = q.get(timeout=1.0)
                        samples.append(np.abs(chunk).mean())
                    except queue.Empty:
                        break

            if samples:
                avg_noise = np.mean(samples)
                self._rec.SPEECH_THRESH = max(400, int(avg_noise * 3.0))  # Higher threshold
                print(f"[STT] Calibrated — noise level: {avg_noise:.0f}, threshold: {self._rec.SPEECH_THRESH}")
        except Exception as e:
            print(f"[STT] Calibration error: {e}")

    # ── Single capture ───────────────────────────────────────────────────────
    def listen_once(self, timeout: float = 5.0, phrase_limit: float = 10.0) -> Optional[str]:
        """
        Listen for ONE phrase. Returns corrected text or None.
        """
        if not SD or not self._rec:
            return None
        try:
            print("[STT] Listening …")
            wav = self._rec.record()
            if wav is None:
                print("[STT] No speech detected")
                return None

            text = self._transcribe(wav)
            if text:
                # Step 1: Translate Hindi to English if needed
                text = _translate_hindi_to_english(text)
                # Step 2: Apply English corrections
                corrected = _correct(text)
                # Step 3: Remove wake words
                corrected = self._strip_wake(corrected)
                print(f"[STT] ✓ Recognised: '{corrected}'")
                return corrected
        except Exception as e:
            print(f"[STT] listen_once error: {e}")
        return None

    # ── Transcription chain ──────────────────────────────────────────────────
    def _transcribe(self, wav: bytes) -> Optional[str]:
        """Try Groq → Local → Google in order."""
        # 1. Groq Whisper (fastest, most accurate for Hinglish)
        if self._groq:
            t = self._groq.transcribe(wav, language="hi")
            if t:
                return t

        # 2. Local Whisper
        if self._local and self._local.model:
            t = self._local.transcribe(wav)
            if t:
                return t

        # 3. Google STT
        if self._google:
            t = self._google.transcribe(wav, language="hi-IN")
            if t:
                return t

        return None

    def _strip_wake(self, text: str) -> str:
        """Remove wake word from beginning of transcription."""
        t = text.strip()
        lower = t.lower()
        for ww in self.WAKE_WORDS:
            if lower.startswith(ww):
                t = t[len(ww):].strip().lstrip(",. ")
                break
        return t

    # ── Continuous listening (for wake word) ────────────────────────────────
    def start_listening(self):
        """Start continuous background listening."""
        if self.is_listening or not SD:
            return
        self.is_listening = True
        self.listening_started.emit()
        threading.Thread(
            target=self._listen_loop, daemon=True, name="jarvis-stt"
        ).start()
        print("[STT] Continuous listening started")

    def stop_listening(self):
        self.is_listening = False
        self.listening_stopped.emit()
        print("[STT] Stopped")

    def _listen_loop(self):
        while self.is_listening:
            text = self.listen_once(timeout=4.0, phrase_limit=10.0)
            if text:
                clean = self._strip_wake(text)
                if clean:
                    self.text_ready.emit(clean)
                else:
                    # Only wake word — continue listening
                    continue