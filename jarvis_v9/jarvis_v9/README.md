# 🤖 JARVIS OMEGA V9

AI-powered desktop assistant with full computer control, screen vision, and self-learning.

## ✨ V9 Features

| Feature | Description |
|---------|-------------|
| 🖱️ **Computer Control** | Mouse, keyboard, browser, window management, system info |
| 👁️ **Screen Vision** | OCR (EasyOCR + Tesseract), AI vision (Gemini/Ollama), element detection |
| 🧠 **Self-Learning** | Skill learning, preference memory, action feedback, training data export |
| 🔮 **Floating Orb** | ESC mode — transparent, frameless, draggable assistant orb |
| 🗣️ **Speech** | Edge TTS + pyttsx3, Whisper STT (Groq/Google/local) |
| 🌐 **Multi-API** | Groq, Cerebras, SambaNova, OpenRouter, NVIDIA, Google, Ollama |

## 🚀 Quick Start

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Copy and fill API keys
copy .env.example .env
# Edit .env with your keys

# 3. Run
python main.py
```

## 🎮 Controls

| Key | Action |
|-----|--------|
| `SPACE` | Start voice command |
| `ESC` | Toggle orb mode / minimize |
| `Ctrl+J` | Show chat panel |
| `Ctrl+Q` | Quit |

## ⚙️ Settings

Edit `config/settings.json`:

```json
{
  "V9_NEW": {
    "esc_orb_mode": false,      // true = floating orb, false = full GUI
    "vision_enabled": true,      // Screen reading
    "learning_enabled": true,    // Self-improvement
    "computer_control_enabled": true
  }
}
```

## 🧠 Teaching JARVIS

Say: *"When I say 'work setup', open Chrome, VS Code, and Spotify"*

Or use the tray menu: **Teach JARVIS**

## 📦 Project Structure

```
jarvis_v9/
├── config/settings.json
├── core/brain.py          # AI brain with learning & vision
├── gui/
│   ├── main_window.py     # Full GUI (V8 style)
│   └── orb_window.py      # ESC floating orb
├── learning/trainer.py    # Self-learning system
├── speech/
│   ├── stt_engine.py      # Speech-to-text
│   └── tts_engine.py        # Text-to-speech
├── tools/automation.py    # Computer control
├── vision/screen_vision.py # Screen OCR + AI vision
├── main.py                # Entry point
└── requirements.txt
```

## 🔗 Ollama Models (Local AI)

```bash
ollama pull llama3.2          # Chat
ollama pull llava             # Vision
ollama pull codellama         # Code
ollama pull deepseek-r1       # Reasoning
```

---
**Made with ❤️ by JARVIS AI**
