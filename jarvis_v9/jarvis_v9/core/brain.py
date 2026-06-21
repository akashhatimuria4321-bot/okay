"""
core/brain.py — JARVIS OMEGA V9
V9 CHANGES:
 1. Integrated LearningHub — self-learning, skill memory, preference tracking
 2. Integrated Vision — screen reading via vision/screen_vision.py
 3. New Ollama advanced models (vision, chat, code, reasoning)
 4. Action extraction enhanced for V9 actions
 5. System prompt includes learned preferences
 6. Screen context injection for vision commands
 7. Feedback loop for action success tracking
"""
from __future__ import annotations

import os, re, json, time, sqlite3, threading, concurrent.futures
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent

try:
    import requests
    REQ = True
except ImportError:
    REQ = False

try:
    import importlib
    _ddg_mod = importlib.import_module("duckduckgo_search")
    DDGS = getattr(_ddg_mod, "DDGS", None)
    DDG = DDGS is not None
except Exception:
    DDG = False

# ═══════════════════════════════════════════════════════════════════════════
# MEMORY
# ═══════════════════════════════════════════════════════════════════════════
class Memory:
    def __init__(self):
        db = BASE / "data" / "memory.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY, user_msg TEXT, ai_msg TEXT, ts TEXT)""")
        self.conn.commit()
        self.short_term: List[dict] = []

    def save(self, u: str, a: str):
        with self._lock:
            self.conn.execute(
                "INSERT INTO conversations(user_msg,ai_msg,ts) VALUES(?,?,?)",
                (u, a, datetime.now().isoformat()))
            self.conn.execute(
                "DELETE FROM conversations WHERE id NOT IN "
                "(SELECT id FROM conversations ORDER BY id DESC LIMIT 300)")
            self.conn.commit()
            self.short_term.append({"user": u, "assistant": a})
            if len(self.short_term) > 14:
                self.short_term = self.short_term[-14:]

    def context(self) -> List[dict]:
        return self.short_term[-8:]

# ═══════════════════════════════════════════════════════════════════════════
# INSTANT COMMAND ROUTER (zero API calls for common commands)
# ═══════════════════════════════════════════════════════════════════════════
_INSTANT = {
    r'\b(time|waqt|samay|kitne baje|what time)\b':
        lambda: f"Sir, abhi {datetime.now():%I:%M %p} baj rahe hain.",
    r'\b(aaj|today|aaj ki date|what.*date|date kya)\b':
        lambda: f"Aaj {datetime.now():%A, %d %B %Y} hai, Sir.",
    r'\b(hello|hi|hey|namaste|hola|salaam)\b':
        lambda: _greet(),
    r'\b(kaisa|how are you|theek ho|sab theek)\b':
        lambda: "Main bilkul theek hoon, Sir! Aap batao, kya kaam hai?",
    r'\b(shukriya|thanks|thank you|dhanyawad)\b':
        lambda: "Koi baat nahi, Sir. Aur kuch kaam ho toh batao.",
    r'\b(mera naam|my name|naam kya)\b':
        lambda: f"Aapka naam {_SETTINGS.get('user_name','Sir')} hai.",
}

_SETTINGS: dict = {}

def _greet() -> str:
    h = datetime.now().hour
    if h < 12: t = "Good morning"
    elif h < 17: t = "Good afternoon"
    else: t = "Good evening"
    return f"{t}, Sir! JARVIS V9 hazir hai. Kya kaam hai aapka?"

def instant_route(text: str) -> Optional[str]:
    for pat, fn in _INSTANT.items():
        if re.search(pat, text, re.I):
            return fn()
    return None

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — V9 with Computer Control & Learning
# ═══════════════════════════════════════════════════════════════════════════
SYS = """You are JARVIS, an AI assistant running on a Windows laptop.
User name: {name}. Current time: {time}.

{learned_prefs}

LANGUAGE RULE — CRITICAL:
- Always reply in HINGLISH: mix of Hindi words written in ENGLISH/ROMAN script + English.
- Example: "Sir, main abhi yeh kaam kar deta hoon. Chrome khul jayega thodi der mein."
- NEVER use Devanagari script (Hindi letters like क ख ग). Only Roman letters.
- Keep it natural — the way Indians speak in WhatsApp messages.

CAPABILITIES: You can control the user's computer. When you need to perform an action,
embed a JSON block ANYWHERE in your response using this exact format:

{{"action":"ACTION_NAME","target":"TARGET"}}

AVAILABLE ACTIONS:
# ── Apps ──
- open_app (target: app name like "chrome", "notepad", "spotify")
- close_app (target: app name)
- minimize_app (target: app name)
- maximize_app (target: app name)

# ── Web ──
- search_web (target: search query)
- search_youtube (target: search query)
- play_music (target: song name)
- open_url (target: full URL)
- open_browser (target: URL or empty for Google)

# ── Mouse ──
- mouse_move (target: "x,y")
- mouse_click (target: "")
- double_click (target: "x,y" or empty)
- right_click (target: "x,y" or empty)
- drag_to (target: "x,y")
- drag_rel (target: "x,y")
- mouse_scroll_up / mouse_scroll_down (target: "")
- scroll_left / scroll_right (target: "")

# ── Keyboard ──
- type_text (target: text to type)
- hotkey (target: "ctrl+c" or "alt+tab" etc)

# ── Screen & Vision ──
- screenshot (target: "")
- read_screen (target: "")
- click_text (target: text visible on screen to click)
- find_and_click (target: text to find and click)

# ── Window ──
- focus_window (target: window title pattern)
- list_windows (target: "")
- resize_window (target: "title,width,height")
- move_window (target: "title,x,y")

# ── System ──
- volume_up / volume_down / mute (target: "")
- lock_screen (target: "")
- system_info (target: "")
- list_processes (target: process name filter or empty)
- save_file / save_as (target: app name)

# ── Browser Automation ──
- fill_form (target: "field_label|text_to_type")

RULES:
1. ALWAYS include ACTION tag when user asks to do something on the computer.
2. Keep replies short and direct — 1-3 sentences max for simple tasks.
3. Address the user as Sir.
4. Do NOT use Devanagari — only Roman-script Hinglish.
5. Do NOT describe your own speech.
6. For screen-related commands, use read_screen or find_and_click.
7. When user says "open browser and search X", use open_browser + search_web.
"""

def _sys_prompt(name: str) -> str:
    prefs = ""
    if _LEARNED_PREFS:
        prefs = "\nLEARNED PREFERENCES:\n" + _LEARNED_PREFS
    return SYS.format(name=name, time=datetime.now().strftime("%I:%M %p, %A"), learned_prefs=prefs)

_LEARNED_PREFS: str = ""

# ═══════════════════════════════════════════════════════════════════════════
# ACTION EXTRACTOR — V9 Enhanced
# ═══════════════════════════════════════════════════════════════════════════
def extract_actions(response: str) -> List[dict]:
    actions = []
    # Method 1: Find all JSON-like blocks
    for match in re.finditer(r'\{[^{}]*"action"[^{}]*\}', response):
        try:
            obj = json.loads(match.group())
            if "action" in obj and obj["action"]:
                actions.append(obj)
        except json.JSONDecodeError:
            pass

    # Method 2: More aggressive pattern for nested JSON
    if not actions:
        for match in re.finditer(r'"action"\s*:\s*"([^"]+)"', response):
            action_name = match.group(1)
            target_match = re.search(r'"target"\s*:\s*"([^"]*)"', response[match.start():match.start()+200])
            target = target_match.group(1) if target_match else ""
            actions.append({"action": action_name, "target": target})

    if actions:
        print(f"[BRAIN] Extracted {len(actions)} action(s): {actions}")
    return actions


def strip_actions(response: str) -> str:
    cleaned = re.sub(r'\s*\{[^{}]*"action"[^{}]*\}\s*', ' ', response)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

# ═══════════════════════════════════════════════════════════════════════════
# WEB SEARCH
# ═══════════════════════════════════════════════════════════════════════════
def web_search(query: str, n: int = 5) -> str:
    if not DDG:
        return ""
    try:
        with DDGS() as d:
            results = list(d.text(query, max_results=n))
            return "\n".join(
                f"• {r.get('title','')}: {r.get('body','')[:150]}"
                for r in results
            )
    except Exception as e:
        print(f"[SEARCH] {e}")
        return ""

def needs_search(text: str) -> bool:
    instant_only = [
        r'\b(time|waqt|samay|kitne baje)\b',
        r'\b(aaj|today|date)\b',
        r'\b(hello|hi|hey|namaste)\b',
    ]
    for pat in instant_only:
        if re.search(pat, text, re.I):
            return False

    triggers = [
        "search", "find online", "latest", "news", "price",
        "weather", "who is", "what is", "how to", "current",
        "khojo", "dhundo", "batao", "recently", "stock",
        "score", "result", "match", "movie", "release",
    ]
    tl = text.lower()
    return any(t in tl for t in triggers)

# ═══════════════════════════════════════════════════════════════════════════
# API CALLERS
# ═══════════════════════════════════════════════════════════════════════════
_HEADERS_JSON = {"Content-Type": "application/json"}

def _post(url: str, key: str, body: dict, timeout: int) -> Optional[str]:
    if not REQ:
        return None
    headers = {**_HEADERS_JSON, "Authorization": f"Bearer {key}"}
    try:
        r = requests.post(url, json=body, headers=headers,
                          timeout=(4, timeout))
        if r.status_code == 200:
            data = r.json()
            return data["choices"][0]["message"]["content"]
        print(f"[API] {url.split('/')[2]} → HTTP {r.status_code}: {r.text[:120]}")
        if r.status_code == 401:
            print(f"[API] ⚠ 401 Unauthorized — key is invalid or expired.")
        elif r.status_code == 429:
            print(f"[API] ⚠ 429 Rate limit — too many requests. Wait a moment.")
    except requests.exceptions.Timeout:
        print(f"[API] {url.split('/')[2]} timed out")
    except Exception as e:
        print(f"[API] {url.split('/')[2]} error: {e}")
    return None

def call_groq(key: str, model: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not key:
        return None
    return _post(
        "https://api.groq.com/openai/v1/chat/completions",
        key,
        {"model": model, "messages": msgs, "temperature": 0.7, "max_tokens": tok},
        timeout=6
    )

def call_cerebras(key: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not key or not key.startswith("csk-"):
        return None
    return _post(
        "https://api.cerebras.ai/v1/chat/completions",
        key,
        {"model": "llama3.1-8b", "messages": msgs, "temperature": 0.7, "max_tokens": tok},
        timeout=5
    )

def call_sambanova(key: str, msgs: list, tok: int = 1024) -> Optional[str]:
    if not key:
        return None
    uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pat, key, re.I):
        print("[API] SambaNova key is not a valid UUID — skipping")
        return None
    return _post(
        "https://api.sambanova.ai/v1/chat/completions",
        key,
        {"model": "Meta-Llama-3.1-8B-Instruct", "messages": msgs,
         "temperature": 0.7, "max_tokens": tok},
        timeout=8
    )

def call_openrouter(key: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not key:
        return None
    uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pat, key, re.I):
        print("[API] OpenRouter key is truncated/invalid UUID — skipping.")
        return None
    return _post(
        "https://openrouter.ai/api/v1/chat/completions",
        key,
        {"model": "google/gemma-2-9b-it:free", "messages": msgs,
         "temperature": 0.7, "max_tokens": tok},
        timeout=10
    )

def call_nvidia(key: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not key or not key.startswith("nvapi-"):
        return None
    return _post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        key,
        {"model": "meta/llama-3.1-8b-instruct", "messages": msgs,
         "temperature": 0.7, "max_tokens": tok},
        timeout=10
    )

def call_google(key: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not key or not key.startswith("AIza"):
        return None
    if not REQ:
        return None
    try:
        contents = []
        for m in msgs:
            role = "user" if m["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        body = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": tok, "temperature": 0.7}
        }
        r = requests.post(url, json=body, timeout=(4, 8))
        if r.status_code == 200:
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"[API] Google → HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[API] Google error: {e}")
    return None

def call_ollama(url: str, model: str, msgs: list, tok: int = 512) -> Optional[str]:
    if not REQ or not url:
        return None
    try:
        body = {
            "model": model,
            "messages": msgs,
            "stream": False,
            "options": {"num_predict": tok, "temperature": 0.7}
        }
        r = requests.post(f"{url}/api/chat", json=body, timeout=(3, 20))
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "").strip() or None
        print(f"[OLLAMA] HTTP {r.status_code}: {r.text[:80]}")
    except requests.exceptions.ConnectionError:
        print("[OLLAMA] Connection refused — is Ollama running? Run: ollama serve")
    except Exception as e:
        print(f"[OLLAMA] error: {e}")
    return None

# ═══════════════════════════════════════════════════════════════════════════
# RACE ENGINE
# ═══════════════════════════════════════════════════════════════════════════
def race(callables: list, global_timeout: float = 8.0) -> Optional[str]:
    if not callables:
        return None

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(callables),
        thread_name_prefix="jarvis-race") as pool:
        futures = {pool.submit(fn): fn for fn in callables}
        try:
            for future in concurrent.futures.as_completed(
                futures, timeout=global_timeout):
                try:
                    result = future.result(timeout=0)
                    if result and result.strip():
                        for f in futures:
                            f.cancel()
                        return result
                except concurrent.futures.CancelledError:
                    pass
                except Exception as e:
                    print(f"[RACE] future error: {e}")
        except concurrent.futures.TimeoutError:
            print("[RACE] global timeout reached")
    return None

# ═══════════════════════════════════════════════════════════════════════════
# TASK ROUTER
# ═══════════════════════════════════════════════════════════════════════════
class TaskRouter:
    def __init__(self, settings: dict):
        self.s = settings

    def _k(self, name: str) -> str:
        return self.s.get(f"{name}_api_key", "")

    def _offline(self) -> bool:
        return bool(self.s.get("offline_mode", False))

    def _ollama_caller(self, msgs: list, model: str = None) -> Optional[callable]:
        url = self.s.get("ollama_url", "http://localhost:11434")
        if model is None:
            model = self.s.get("ollama_model", "llama3.2")
        if url and model:
            return lambda u=url, m=model: call_ollama(u, m, msgs)
        return None

    def build_chat_callers(self, msgs: list) -> list:
        callers = []
        if self._offline():
            fn = self._ollama_caller(msgs)
            if fn:
                callers.append(fn)
            return callers

        k_cerebras = self._k("cerebras")
        if k_cerebras:
            callers.append(lambda k=k_cerebras: call_cerebras(k, msgs))

        k_groq = self._k("groq")
        if k_groq:
            callers.append(lambda k=k_groq: call_groq(k, "llama-3.1-8b-instant", msgs, 400))

        k_sambanova = self._k("sambanova")
        if k_sambanova:
            callers.append(lambda k=k_sambanova: call_sambanova(k, msgs))

        k_openrouter = self._k("openrouter")
        if k_openrouter:
            callers.append(lambda k=k_openrouter: call_openrouter(k, msgs))

        k_nvidia = self._k("nvidia")
        if k_nvidia:
            callers.append(lambda k=k_nvidia: call_nvidia(k, msgs))

        k_google = self._k("google")
        if k_google:
            callers.append(lambda k=k_google: call_google(k, msgs))

        if k_groq:
            callers.append(lambda k=k_groq: call_groq(k, "llama-3.3-70b-versatile", msgs, 700))

        fn = self._ollama_caller(msgs)
        if fn:
            callers.append(fn)

        return callers

    def build_search_callers(self, msgs: list) -> list:
        callers = []
        if self._offline():
            fn = self._ollama_caller(msgs)
            if fn:
                callers.append(fn)
            return callers

        k_sambanova = self._k("sambanova")
        if k_sambanova:
            callers.append(lambda k=k_sambanova: call_sambanova(k, msgs, 800))

        k_groq = self._k("groq")
        if k_groq:
            callers.append(lambda k=k_groq: call_groq(k, "llama-3.1-8b-instant", msgs, 600))

        return callers or self.build_chat_callers(msgs)

    def build_screen_callers(self, msgs: list) -> list:
        callers = []
        if self._offline():
            # Use vision model for screen tasks
            vision_model = self.s.get("ollama_vision_model", "llava")
            fn = self._ollama_caller(msgs, model=vision_model)
            if fn:
                callers.append(fn)
            return callers

        k_groq = self._k("groq")
        if k_groq:
            callers.append(lambda k=k_groq: call_groq(k, "llama-3.3-70b-versatile", msgs, 500))

        k_cerebras = self._k("cerebras")
        if k_cerebras:
            callers.append(lambda k=k_cerebras: call_cerebras(k, msgs))

        return callers or self.build_chat_callers(msgs)

    def build_code_callers(self, msgs: list) -> list:
        callers = []
        if self._offline():
            code_model = self.s.get("ollama_advanced_models", {}).get("code", ["codellama"])[0]
            fn = self._ollama_caller(msgs, model=code_model)
            if fn:
                callers.append(fn)
            return callers

        k_groq = self._k("groq")
        if k_groq:
            callers.append(lambda k=k_groq: call_groq(k, "llama-3.3-70b-versatile", msgs, 1024))

        return callers or self.build_chat_callers(msgs)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN BRAIN — V9 with Learning & Vision
# ═══════════════════════════════════════════════════════════════════════════
class JarvisBrain:
    def __init__(self, settings: dict):
        global _SETTINGS, _LEARNED_PREFS
        self.settings = settings
        _SETTINGS = settings
        self.memory = Memory()
        self.router = TaskRouter(settings)
        self._screen_ctx = ""
        self.automation = None
        self.learning = None
        self.vision_enabled = True

        # V9: Initialize Learning Hub
        if settings.get("V9_NEW", {}).get("learning_enabled", True):
            try:
                from learning.trainer import get_learning_hub
                self.learning = get_learning_hub()
                _LEARNED_PREFS = self.learning.get_system_prompt_additions()
                print(f"[BRAIN] ✓ Learning hub ready. Injected prefs: {_LEARNED_PREFS[:80] if _LEARNED_PREFS else 'None'}")
            except Exception as e:
                print(f"[BRAIN] Learning hub init error: {e}")

        self.vision_enabled = settings.get("V9_NEW", {}).get("vision_enabled", True)
        print(f"[BRAIN] ✓ V9 brain ready | Vision: {self.vision_enabled}")
        if settings.get("offline_mode"):
            print(f"[BRAIN] 🔌 Offline mode — Ollama @ {settings.get('ollama_url')}")

    def _msgs(self, user_input: str) -> list:
        msgs = [{"role": "system",
                 "content": _sys_prompt(self.settings.get("user_name", "Sir"))}]
        for h in self.memory.context():
            msgs.append({"role": "user", "content": h["user"]})
            msgs.append({"role": "assistant", "content": h["assistant"]})
        msgs.append({"role": "user", "content": user_input})
        return msgs

    def update_screen_context(self, text: str):
        self._screen_ctx = text[:600]

    def process(self, text: str, task_hint: str = "chat") -> Tuple[str, List[dict]]:
        t0 = time.time()

        # 1. Instant router (0ms, no API)
        quick = instant_route(text)
        if quick:
            self.memory.save(text, quick)
            print(f"[BRAIN] instant {time.time()-t0:.3f}s")
            return quick, []

        # 2. Check learned skills first
        if self.learning:
            skill_actions = self.learning.process_user_input(text)
            if skill_actions:
                print(f"[BRAIN] Learned skill matched: {skill_actions}")
                return "Skill execute kar raha hoon, Sir.", skill_actions

        # 3. Build input
        user_input = text
        if needs_search(text):
            n_results = self.settings.get("V9_NEW", {}).get("web_search_results", 5)
            sr = web_search(text, n=n_results)
            if sr:
                user_input = f"{text}\n\n[Web context]\n{sr}"

        # 4. V9: Vision context injection for screen commands
        screen_triggers = ["screen", "dekho", "what do you see", "read screen", 
                          "click on", "find", "what is on my screen", "screen pe"]
        if any(t in text.lower() for t in screen_triggers) and self.vision_enabled:
            try:
                from vision.screen_vision import get_screen_reader
                reader = get_screen_reader(self.settings)
                screen_text = reader.read(use_ai=True)
                user_input += f"\n\n[Current Screen Content]\n{screen_text[:800]}"
                task_hint = "screen"
                print(f"[BRAIN] Vision context injected ({len(screen_text)} chars)")
            except Exception as e:
                print(f"[BRAIN] Vision error: {e}")

        if self._screen_ctx:
            user_input = f"[Screen context: {self._screen_ctx}]\n\n{user_input}"

        msgs = self._msgs(user_input)

        # 5. Pick callers and race
        if task_hint == "screen":
            callers = self.router.build_screen_callers(msgs)
        elif task_hint == "search":
            callers = self.router.build_search_callers(msgs)
        elif task_hint == "code":
            callers = self.router.build_code_callers(msgs)
        else:
            callers = self.router.build_chat_callers(msgs)

        if not callers:
            resp = ("Koi bhi API key nahi mili, Sir. "
                   "Please .env file mein apni keys add karein.")
            return resp, []

        raw = race(callers, global_timeout=10.0)

        if raw:
            print(f"[BRAIN] Raw AI response (first 200 chars): {raw[:200]}")
        else:
            print("[BRAIN] AI returned empty/timeout")
            raw = ("Sab providers timeout ho gaye, Sir. "
                   "Internet connection check karein ya offline mode on karein.")

        # 6. Extract actions
        try:
            actions = extract_actions(raw)
        except Exception as e:
            print(f"[BRAIN] Action extraction error: {e}")
            actions = []

        # 7. Strip actions
        try:
            clean = strip_actions(raw)
        except Exception as e:
            print(f"[BRAIN] Strip actions error: {e}")
            clean = raw

        # 8. Convert Devanagari to Hinglish
        clean = hindi_to_hinglish(clean)

        self.memory.save(text, clean)
        print(f"[BRAIN] {time.time()-t0:.2f}s | {len(actions)} actions | response: {clean[:80]}")
        return clean, actions

    def clear_history(self):
        self.memory.short_term.clear()

    def learn_correction(self, original: str, ai_response: str, user_correction: str, action: dict = None):
        """User says 'No, do it like this...' — learn from it."""
        if self.learning:
            self.learning.correct(original, ai_response, user_correction, action)
            print(f"[BRAIN] Correction learned: {user_correction[:60]}")

    def teach_skill(self, trigger: str, actions: list, description: str = ""):
        """Explicit teaching: 'When I say X, do Y, Z'"""
        if self.learning:
            skill_id = self.learning.teach(trigger, actions, description)
            print(f"[BRAIN] Skill taught: {skill_id}")
            return skill_id
        return None

    def report_action_result(self, action: dict, context: str, success: bool):
        """Report action success/failure for learning."""
        if self.learning:
            self.learning.report_result(action, context, success)

    def export_training_data(self):
        """Export collected data for model fine-tuning."""
        if self.learning:
            path = self.learning.exporter.export_for_ollama()
            print(f"[BRAIN] Training data exported to: {path}")
            return path
        return None

# ═══════════════════════════════════════════════════════════════════════════
# HINDI → HINGLISH
# ═══════════════════════════════════════════════════════════════════════════
_HM = {
    'नमस्ते': 'namaste', 'धन्यवाद': 'dhanyavaad', 'शुक्रिया': 'shukriya',
    'हाँ': 'haan', 'नहीं': 'nahin', 'हा': 'haa',
    'ठीक': 'theek', 'बहुत': 'bahut', 'अच्छा': 'achha', 'जल्दी': 'jaldi',
    'करो': 'karo', 'करें': 'karein', 'करता': 'karta', 'करती': 'karti',
    'बताओ': 'batao', 'बताइए': 'bataiye', 'देखो': 'dekho', 'सुनो': 'suno',
    'खोलो': 'kholo', 'बंद': 'band', 'चालू': 'chaalu',
    'क्या': 'kya', 'कैसे': 'kaise', 'कहाँ': 'kahaan', 'कब': 'kab',
    'क्यों': 'kyun', 'कौन': 'kaun', 'कितना': 'kitna', 'कितने': 'kitne',
    'मैं': 'main', 'आप': 'aap', 'हम': 'hum', 'वह': 'woh', 'यह': 'yeh',
    'मेरा': 'mera', 'आपका': 'aapka', 'हमारा': 'hamara',
    'अभी': 'abhi', 'आज': 'aaj', 'कल': 'kal', 'परसों': 'parso',
    'सुबह': 'subah', 'शाम': 'shaam', 'रात': 'raat', 'दोपहर': 'dopahar',
    'बजे': 'baje', 'मिनट': 'minute', 'घंटे': 'ghante',
    'हूँ': 'hoon', 'है': 'hai', 'हैं': 'hain', 'था': 'tha', 'थी': 'thi',
    'होगा': 'hoga', 'होगी': 'hogi', 'हो': 'ho', 'गया': 'gaya', 'गई': 'gayi',
    'रहा': 'raha', 'रही': 'rahi', 'रहे': 'rahe',
    'और': 'aur', 'या': 'ya', 'लेकिन': 'lekin', 'क्योंकि': 'kyunki',
    'के': 'ke', 'की': 'ki', 'का': 'ka', 'में': 'mein', 'पर': 'par',
    'से': 'se', 'को': 'ko', 'ने': 'ne', 'तो': 'to', 'भी': 'bhi',
    'यहाँ': 'yahaan', 'वहाँ': 'wahaan', 'ऊपर': 'upar', 'नीचे': 'neeche',
    'सही': 'sahi', 'गलत': 'galat', 'पूरा': 'poora', 'थोड़ा': 'thoda',
    'बड़ा': 'bada', 'छोटा': 'chhota', 'नया': 'naya', 'पुराना': 'purana',
    'काम': 'kaam', 'नाम': 'naam', 'बात': 'baat', 'जगह': 'jagah',
    'मदद': 'madad', 'समझ': 'samajh', 'जानकारी': 'jaankari',
    'कोशिश': 'koshish', 'जरूरत': 'zaroorat', 'तरीका': 'tarika',
    'दोबारा': 'dobara', 'जारी': 'jaari', 'शुरू': 'shuru', 'खत्म': 'khatam',
    'साहब': 'sahab', 'जी': 'ji', 'सर': 'Sir',
    'खोलें': 'kholein', 'बंद करें': 'band karein', 'खोज': 'khoj',
    'डाउनलोड': 'download', 'इंटरनेट': 'internet',
}

def hindi_to_hinglish(text: str) -> str:
    for h, r in _HM.items():
        text = text.replace(h, r)
    text = re.sub(r'[\u0900-\u097F]+', lambda m: f'[{m.group()}]', text)
    return text
