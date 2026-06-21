"""
gui/main_window.py — JARVIS OMEGA V8 with V7 GUI (FIXED for task execution)
Layout: Full-screen frameless. Starfield background. Arc reactor + clock centred.
Chat panel RIGHT. Output panel LEFT. Assistant ball (minimise).
All V8 features: Hinglish, API status, offline mode, better STT, action colors.
FIXED: Now properly calls automation.execute() with correct action dict format.
Python 3.14.5 | PyQt6
"""
from __future__ import annotations

import sys, math, random, time, threading, re
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QFrame, QScrollArea,
    QApplication, QSystemTrayIcon, QMenu, QSizePolicy, QCheckBox,
    QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QRadialGradient, QPixmap, QIcon, QKeySequence, QShortcut,
    QTextCursor, QTextCharFormat,
)

BASE = Path(__file__).resolve().parent.parent

# ── Palette ──────────────────────────────────────────────────────────────────
C_CYAN = QColor(0, 210, 255)
C_GREEN = QColor(0, 255, 140)
C_ORANGE = QColor(255, 165, 30)
C_RED = QColor(255, 60, 60)
C_BG = QColor(3, 7, 20)
C_PANEL = QColor(7, 13, 28)
C_TEXT = QColor(185, 215, 240)
C_MUTED = QColor(60, 90, 110)
C_ACCENT = QColor(0, 212, 255)
C_KEY_OK = QColor(0, 255, 136)
C_KEY_BAD = QColor(255, 68, 68)
C_KEY_MISS = QColor(136, 136, 136)

_PANEL_SS = """
QFrame {{
    background: rgba(7,13,28,{alpha});
    border: 1px solid rgba(0,200,255,{border});
    border-radius: 14px;
}}
QTextEdit {{
    background: transparent; color: #b8d4ee;
    font-family: 'Segoe UI'; font-size: 12px; border: none; padding: 6px;
}}
QLineEdit {{
    background: rgba(0,20,50,100); color: #9ec8ef;
    font-family: 'Segoe UI'; font-size: 12px;
    border: 1px solid rgba(0,200,255,55); border-radius: 8px; padding: 6px 10px;
}}
QLineEdit:focus {{ border: 1px solid rgba(0,220,255,130); }}
QPushButton {{
    background: rgba(0,120,180,120); color: #ffffff;
    font-family: 'Segoe UI'; font-size: 11px; font-weight: bold;
    border: none; border-radius: 8px; padding: 6px 14px;
}}
QPushButton:hover {{ background: rgba(0,160,220,180); }}
QPushButton:pressed {{ background: rgba(0,100,150,200); }}
QLabel {{ background: transparent; }}
QScrollBar:vertical {{
    background: rgba(0,0,0,0); width: 5px;
}}
QScrollBar::handle:vertical {{
    background: rgba(0,180,240,50); border-radius: 2px;
}}
QCheckBox {{ color: #b8d4ee; spacing: 6px; font-size: 11px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid rgba(0,200,255,80); }}
QCheckBox::indicator:checked {{ background: rgba(0,200,255,120); }}
"""

def _pss(alpha: int, border: int) -> str:
    return _PANEL_SS.format(alpha=alpha, border=border)


# ═══════════════════════════════════════════════════════════════════════════
# STARFIELD
# ═══════════════════════════════════════════════════════════════════════════
class _Star:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.reset()
    def reset(self):
        self.x = random.randint(0, max(self.w, 1))
        self.y = random.randint(0, max(self.h, 1))
        self.size = random.uniform(0.4, 2.0)
        self.speed = random.uniform(0.08, 0.4)
        self.base = random.randint(35, 140)
        self.phase = random.uniform(0, 6.28)
        self.dt = random.uniform(0.02, 0.05)
    def step(self):
        self.y -= self.speed
        self.phase = (self.phase + self.dt) % 6.28
        if self.y < 0:
            self.y = self.h
    @property
    def alpha(self) -> int:
        return max(0, min(255, int(self.base * (0.5 + 0.5 * math.sin(self.phase)))))

class StarfieldWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._stars: list[_Star] = []
        QTimer(self, timeout=self._tick, interval=18).start()

    def _tick(self):
        w, h = self.width(), self.height()
        if not self._stars and w > 10:
            self._stars = [_Star(w, h) for _ in range(160)]
        for s in self._stars:
            s.w, s.h = w, h
            s.step()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(3, 7, 20))
        g.setColorAt(0.5, QColor(5, 11, 26))
        g.setColorAt(1.0, QColor(3, 7, 20))
        p.fillRect(self.rect(), g)
        for s in self._stars:
            p.setPen(QPen(QColor(160, 210, 255, s.alpha), s.size))
            p.drawPoint(int(s.x), int(s.y))
        # vignette
        v = QRadialGradient(w/2, h/2, max(w, h)*0.65)
        v.setColorAt(0.0, QColor(0,0,0,0))
        v.setColorAt(1.0, QColor(0,0,0,170))
        p.fillRect(self.rect(), v)
        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# ARC REACTOR
# ═══════════════════════════════════════════════════════════════════════════
class ArcReactor(QWidget):
    def __init__(self, parent=None, size=200):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._pulse = 0.0
        self._mode = "idle"  # idle | listening | thinking | speaking
        QTimer(self, timeout=self._tick, interval=15).start()

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def _tick(self):
        speeds = {"idle": 1.8, "listening": 4.5, "thinking": 6.0, "speaking": 5.0}
        self._angle = (self._angle + speeds.get(self._mode, 2.0)) % 360
        self._pulse = (self._pulse + 0.07) % 6.28
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = self.width() // 2
        OR = cx - 8
        IR = int(OR * 0.64)
        pf = 0.82 + 0.18 * math.sin(self._pulse)

        # Glow rings
        colours = {
            "idle": C_CYAN,
            "listening": C_GREEN,
            "thinking": C_ORANGE,
            "speaking": QColor(100, 200, 255),
        }
        ring_col = colours.get(self._mode, C_CYAN)

        for i in range(8, 0, -1):
            alpha = int(22 * pf / i)
            p.setPen(QPen(QColor(0, 200, 255, alpha), i * 3))
            p.drawEllipse(cx - OR, cy - OR, OR*2, OR*2)

        # Outer ring
        p.setPen(QPen(ring_col, 2.5))
        p.drawEllipse(cx - OR, cy - OR, OR*2, OR*2)

        # Spinning arc
        p.setPen(QPen(QColor(0, 235, 255, 255), 4,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(cx-OR+3, cy-OR+3, (OR-3)*2, (OR-3)*2,
                  int(self._angle*16), int(115*16))

        # Counter-arc
        p.setPen(QPen(QColor(60, 180, 255, 110), 2.5,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(cx-OR+8, cy-OR+8, (OR-8)*2, (OR-8)*2,
                  int(-self._angle*1.6*16), int(75*16))

        # Inner ring
        p.setPen(QPen(QColor(0, 170, 210, 80), 1.5))
        p.drawEllipse(cx-IR, cy-IR, IR*2, IR*2)

        # Centre dot
        dot_r = 5.5 * pf
        p.setBrush(QBrush(ring_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(float(cx), float(cy)), dot_r, dot_r)

        # Label
        labels = {"idle":"JARVIS","listening":"LISTENING","thinking":"THINKING","speaking":"SPEAKING"}
        lbl = labels.get(self._mode, "JARVIS")
        f = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QPen(QColor(190, 225, 255, 200)))
        tw = p.fontMetrics().horizontalAdvance(lbl)
        p.drawText(cx - tw//2, cy + 6, lbl)
        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# CLOCK + DATE
# ═══════════════════════════════════════════════════════════════════════════
class ClockLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "color:#9ec8ef; font-family:'Segoe UI',monospace;"
            "font-size:52px; font-weight:200; letter-spacing:6px; background:transparent;")
        QTimer(self, timeout=self._tick, interval=1000).start()
        self._tick()
    def _tick(self): self.setText(datetime.now().strftime("%H:%M"))

class DateLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "color:#3a5868; font-family:'Segoe UI'; font-size:10px;"
            "letter-spacing:3px; background:transparent;")
        QTimer(self, timeout=self._tick, interval=60000).start()
        self._tick()
    def _tick(self): self.setText(datetime.now().strftime("%A, %d %B %Y").upper())


# ═══════════════════════════════════════════════════════════════════════════
# STATUS BAR
# ═══════════════════════════════════════════════════════════════════════════
class StatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(
            "QFrame{background:rgba(0,5,18,180);border-top:1px solid rgba(0,200,255,25);}"
            "QLabel{color:#3a5060;font-family:'Segoe UI';font-size:10px;background:transparent;}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        self.left = QLabel("SYSTEM ONLINE")
        self.left.setStyleSheet("color:#00c0ef; background:transparent;")
        lay.addWidget(self.left)
        lay.addStretch()
        lay.addWidget(QLabel("JARVIS OMEGA V8"))
        lay.addStretch()
        self.right = QLabel("READY")
        lay.addWidget(self.right)

    def set(self, text: str, kind: str = "normal"):
        self.right.setText(text.upper())
        c = {"error":"#ff4040","success":"#30ff80","warning":"#ffaa00"}.get(kind,"#3a5060")
        self.right.setStyleSheet(f"color:{c};background:transparent;")


# ═══════════════════════════════════════════════════════════════════════════
# CHAT PANEL (right side) — V8 features added
# ═══════════════════════════════════════════════════════════════════════════
class ChatPanel(QFrame):
    command_entered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._alpha = 0
        self._apply(0, 0)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        hdr = QLabel("◈ JARVIS INTERFACE ◈")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(
            "color:#00c0ef;font-family:'Segoe UI';font-size:10px;"
            "font-weight:bold;letter-spacing:4px;background:transparent;")
        lay.addWidget(hdr)

        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.document().setMaximumBlockCount(400)
        self.display.setFont(QFont("Segoe UI", 12))
        # V8-style bubble colors in V7 panel
        self.display.document().setDefaultStyleSheet("""
            .user { color: #55ee88; font-weight: bold; }
            .ai { color: #00c8ff; }
            .act { color: #aaffcc; font-style: italic; font-size: 11px; }
            .err { color: #ff8888; font-style: italic; font-size: 11px; }
            .sys { color: #5a7a9a; font-size: 10px; }
            .time { color: #3a5868; font-size: 10px; }
        """)
        lay.addWidget(self.display)

        row = QHBoxLayout()
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Type a command or press SPACE to speak…")
        self.inp.returnPressed.connect(self._send)
        row.addWidget(self.inp)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedWidth(46)
        row.addWidget(self.mic_btn)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setFixedWidth(58)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)
        lay.addLayout(row)

    def _apply(self, alpha: int, border: int):
        self._alpha = alpha
        self.setStyleSheet(_pss(alpha, border))

    def show_panel(self):
        self.setVisible(True)
        self.raise_()
        self._fade_to(175)

    def hide_panel(self):
        self._fade_to(0)

    def _fade_to(self, target: int):
        if hasattr(self, "_ft") and self._ft.isActive():
            self._ft.stop()
        self._ft_target = target
        self._ft = QTimer(self)
        self._ft.timeout.connect(self._do_fade)
        self._ft.start(12)

    def _do_fade(self):
        step = 14 if self._ft_target > self._alpha else -14
        v = self._alpha + step
        v = max(0, min(175, v))
        border = int(v * 55 / 175)
        self._apply(v, border)
        if v == 0:
            self._ft.stop()
            self.setVisible(False)
        elif v >= 175:
            self._ft.stop()

    def add_message(self, text: str, sender: str = "JARVIS"):
        ts = datetime.now().strftime("%H:%M:%S")
        if sender == "JARVIS":
            self.display.append(f'<span class="time">[{ts}]</span> <span class="ai">🤖 JARVIS:</span> <span class="ai">{text}</span>')
        elif sender == "USER":
            self.display.append(f'<span class="time">[{ts}]</span> <span class="user">🧑 Sir:</span> <span class="user">{text}</span>')
        elif sender == "ACTION_OK":
            self.display.append(f'<span class="time">[{ts}]</span> <span class="act">✅ {text}</span>')
        elif sender == "ACTION_FAIL":
            self.display.append(f'<span class="time">[{ts}]</span> <span class="err">❌ {text}</span>')
        elif sender == "SYSTEM":
            self.display.append(f'<span class="time">[{ts}]</span> <span class="sys">ℹ {text}</span>')
        else:
            self.display.append(f'<span class="time">[{ts}]</span> {sender}: {text}')
        self.display.verticalScrollBar().setValue(
            self.display.verticalScrollBar().maximum())

    def add_listening(self):
        self.add_message("Listening… (boliye Sir)", "SYSTEM")

    def add_thinking(self):
        self.add_message("Thinking…", "SYSTEM")

    def clear(self):
        self.display.clear()

    def _send(self):
        txt = self.inp.text().strip()
        if not txt:
            return
        self.add_message(txt, "USER")
        self.inp.clear()
        self.command_entered.emit(txt)


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT PANEL (left side) — V8 CMD output integrated
# ═══════════════════════════════════════════════════════════════════════════
class OutputPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._alpha = 0
        self._hidden_to_top = False  # NEW: track if hidden to top
        self._original_height = 440
        self._apply(0, 0)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # Header row with toggle button
        hdr_row = QHBoxLayout()
        hdr = QLabel("◈ OUTPUT ◈")
        hdr.setStyleSheet(
            "color:#00c0ef;font-family:'Segoe UI';font-size:10px;"
            "font-weight:bold;letter-spacing:4px;background:transparent;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        # NEW: Toggle hide-to-top button
        self._toggle_btn = QPushButton("▲")
        self._toggle_btn.setFixedSize(26, 22)
        self._toggle_btn.setStyleSheet(
            "QPushButton{background:rgba(0,200,255,60);color:#00c0ef;"
            "font-size:11px;border-radius:5px;}"
            "QPushButton:hover{background:rgba(0,200,255,120);}")
        self._toggle_btn.setToolTip("Hide to top / Show")
        self._toggle_btn.clicked.connect(self._toggle_top_hide)
        hdr_row.addWidget(self._toggle_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 22)
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,60,60,60);color:#ff8080;"
            "font-size:11px;border-radius:5px;}"
            "QPushButton:hover{background:rgba(255,60,60,130);}")
        close_btn.clicked.connect(self.hide_panel)
        hdr_row.addWidget(close_btn)
        lay.addLayout(hdr_row)

        # Tab buttons
        tab_row = QHBoxLayout()
        self._tabs: dict[str, QPushButton] = {}
        for t in ("SCREEN", "IMAGE", "VIDEO", "INFO", "CMD"):
            btn = QPushButton(t)
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, name=t: self._switch_tab(name))
            self._tabs[t] = btn
            tab_row.addWidget(btn)
        lay.addLayout(tab_row)

        # Scroll content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_lay.setSpacing(6)
        scroll.setWidget(self._content)
        lay.addWidget(scroll)
        self._scroll = scroll

        # CMD output (hidden by default, shown when CMD tab selected)
        self.cmd_output = QTextEdit()
        self.cmd_output.setReadOnly(True)
        self.cmd_output.setFont(QFont("Consolas", 11))
        self.cmd_output.setStyleSheet(
            "background:rgba(0,5,15,180); color:#aaffcc; border:none; "
            "border-radius:6px; padding:6px; font-size:11px;")
        self.cmd_output.setMaximumHeight(200)
        self.cmd_output.setVisible(False)
        lay.addWidget(self.cmd_output)

        # NOW switch to INFO tab (after cmd_output is created)
        self._switch_tab("INFO")

    def _apply(self, alpha: int, border: int):
        self._alpha = alpha
        self.setStyleSheet(_pss(alpha, border))

    def _switch_tab(self, name: str):
        for k, btn in self._tabs.items():
            active = k == name
            btn.setChecked(active)
            c = "#00c0ef" if active else "#2a4050"
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{c};"
                f"font-size:10px;font-weight:bold;border:none;"
                f"border-bottom: {'2px solid #00c0ef' if active else 'none'};}}")
        # Show/hide cmd output
        if hasattr(self, "cmd_output") and self.cmd_output:
            self.cmd_output.setVisible(name == "CMD")

    # NEW: Toggle hide to top (like in video)
    def _toggle_top_hide(self):
        if self._hidden_to_top:
            self._show_from_top()
        else:
            self._hide_to_top()

    def _hide_to_top(self):
        """Animate panel shrinking and moving to top edge."""
        self._hidden_to_top = True
        self._toggle_btn.setText("▼")
        if hasattr(self, "_ht") and self._ht.isActive():
            self._ht.stop()
        self._ht = QTimer(self)
        self._ht.timeout.connect(self._do_hide_to_top)
        self._ht.start(16)
        self._ht_step = 0

    def _do_hide_to_top(self):
        self._ht_step += 1
        progress = min(1.0, self._ht_step / 15)
        # Shrink height
        new_h = int(self._original_height * (1 - progress * 0.85))
        self.setFixedHeight(max(30, new_h))
        # Fade out content
        alpha = int(165 * (1 - progress))
        self._apply(alpha, int(alpha * 50 / 165))
        if progress >= 1.0:
            self._ht.stop()
            self.setFixedHeight(30)
            self._apply(0, 0)

    def _show_from_top(self):
        """Restore panel from top-hidden state."""
        self._hidden_to_top = False
        self._toggle_btn.setText("▲")
        if hasattr(self, "_ht") and self._ht.isActive():
            self._ht.stop()
        self._ht = QTimer(self)
        self._ht.timeout.connect(self._do_show_from_top)
        self._ht.start(16)
        self._ht_step = 0

    def _do_show_from_top(self):
        self._ht_step += 1
        progress = min(1.0, self._ht_step / 15)
        # Grow height
        new_h = int(30 + (self._original_height - 30) * progress)
        self.setFixedHeight(new_h)
        # Fade in
        alpha = int(165 * progress)
        self._apply(alpha, int(alpha * 50 / 165))
        if progress >= 1.0:
            self._ht.stop()
            self.setFixedHeight(self._original_height)
            self._apply(165, 50)

    def show_panel(self):
        self.setVisible(True)
        self.raise_()
        if self._hidden_to_top:
            self._show_from_top()
        else:
            self._fade_to(165)

    def hide_panel(self):
        self._hidden_to_top = False
        self._toggle_btn.setText("▲")
        self._fade_to(0)

    def _fade_to(self, target: int):
        if hasattr(self, "_ft") and self._ft.isActive():
            self._ft.stop()
        self._ft_target = target
        self._ft = QTimer(self)
        self._ft.timeout.connect(self._do_fade)
        self._ft.start(12)

    def _do_fade(self):
        step = 14 if self._ft_target > self._alpha else -14
        v = self._alpha + step
        v = max(0, min(165, v))
        border = int(v * 50 / 165)
        self._apply(v, border)
        if v == 0:
            self._ft.stop()
            self.setVisible(False)
        elif v >= 165:
            self._ft.stop()

    def add_text(self, text: str, tab: str = "INFO"):
        self._switch_tab(tab.upper())
        self.show_panel()
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#b8d4ee;font-size:12px;font-family:'Segoe UI';"
            "padding:4px;background:transparent;")
        self._content_lay.addWidget(lbl)
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum())

    def add_image(self, path_or_pixmap, caption: str = ""):
        self._switch_tab("IMAGE")
        self.show_panel()
        pm = path_or_pixmap if isinstance(path_or_pixmap, QPixmap)             else QPixmap(str(path_or_pixmap))
        if not pm.isNull():
            pm = pm.scaledToWidth(340, Qt.TransformationMode.SmoothTransformation)
            img_lbl = QLabel()
            img_lbl.setPixmap(pm)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_lay.addWidget(img_lbl)
            if caption:
                lbl = QLabel(caption)
                lbl.setStyleSheet("color:#5a8090;font-size:10px;background:transparent;")
                self._content_lay.addWidget(lbl)

    def add_cmd(self, text: str, ok: bool = True):
        self._switch_tab("CMD")
        self.show_panel()
        if hasattr(self, "cmd_output") and self.cmd_output:
            color = "#aaffcc" if ok else "#ff8888"
            icon = "✅" if ok else "❌"
            self.cmd_output.append(f"{icon} {text}")
            self.cmd_output.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self):
        while self._content_lay.count():
            item = self._content_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if hasattr(self, "cmd_output") and self.cmd_output:
            self.cmd_output.clear()


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS DIALOG (replaces V8 sidebar)
# ═══════════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS Settings")
        self.setFixedSize(320, 280)
        self.setStyleSheet(_pss(200, 80))
        self.settings = settings
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        hdr = QLabel("⚡ SETTINGS")
        hdr.setStyleSheet("color:#00c0ef;font-size:14px;font-weight:bold;letter-spacing:3px;")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hdr)

        # Toggles
        self.hinglish_cb = QCheckBox("Hinglish Display")
        self.hinglish_cb.setChecked(bool(self.settings.get("hinglish_display_mode", True)))
        lay.addWidget(self.hinglish_cb)

        self.offline_cb = QCheckBox("Offline Mode (Ollama)")
        self.offline_cb.setChecked(bool(self.settings.get("offline_mode", False)))
        lay.addWidget(self.offline_cb)

        self.tts_cb = QCheckBox("Voice Output (TTS)")
        self.tts_cb.setChecked(True)
        lay.addWidget(self.tts_cb)

        lay.addStretch()

        # Key status
        key_hdr = QLabel("API KEY STATUS")
        key_hdr.setStyleSheet("color:#00c0ef;font-size:10px;font-weight:bold;letter-spacing:2px;")
        lay.addWidget(key_hdr)

        keys = [
            ("Groq", "groq_api_key", "gsk_"),
            ("Cerebras", "cerebras_api_key", "csk-"),
            ("SambaNova", "sambanova_api_key", None),
            ("OpenRouter", "openrouter_api_key", None),
            ("NVIDIA", "nvidia_api_key", "nvapi-"),
            ("Google", "google_api_key", "AIza"),
        ]
        uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

        for name, key, prefix in keys:
            val = self.settings.get(key, "").strip()
            row = QHBoxLayout()
            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(80)
            name_lbl.setStyleSheet("color:#5a7a9a;font-size:10px;")

            if not val:
                status, colour = "✗ Missing", "#888888"
            elif prefix and not val.startswith(prefix):
                status, colour = "⚠ Bad", "#ff4444"
            elif name in ("SambaNova", "OpenRouter") and val:
                if not re.match(uuid_pat, val, re.I):
                    status, colour = "⚠ Bad UUID", "#ff4444"
                else:
                    status, colour = "✓ OK", "#00ff88"
            else:
                status, colour = "✓ OK", "#00ff88"

            stat_lbl = QLabel(status)
            stat_lbl.setStyleSheet(f"color:{colour};font-size:10px;font-weight:bold;")
            row.addWidget(name_lbl)
            row.addWidget(stat_lbl)
            row.addStretch()
            lay.addLayout(row)

        lay.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    def get_settings(self):
        return {
            "hinglish_display_mode": self.hinglish_cb.isChecked(),
            "offline_mode": self.offline_cb.isChecked(),
            "tts_enabled": self.tts_cb.isChecked(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# ASSISTANT BALL (minimised state)
# ═══════════════════════════════════════════════════════════════════════════
class AssistantBall(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(60, 60)
        self._angle = 0.0
        self._pulse = 0.0
        self.setVisible(False)
        QTimer(self, timeout=self._tick, interval=18).start()

    def _tick(self):
        self._angle = (self._angle + 3.5) % 360
        self._pulse = (self._pulse + 0.09) % 6.28
        if self.isVisible():
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = 30
        r = 26
        pf = 0.8 + 0.2 * math.sin(self._pulse)

        # Glow
        gw = QRadialGradient(cx, cy, r*2)
        gw.setColorAt(0, QColor(0, 200, 255, int(45*pf)))
        gw.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(gw))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx-r*2), int(cy-r*2), int(r*4), int(r*4))

        # Body
        g = QRadialGradient(cx-7, cy-7, r*1.2)
        g.setColorAt(0, QColor(12, 45, 90, 210))
        g.setColorAt(1, QColor(3, 10, 25, 200))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(0, 200, 255, 120), 1.5))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)

        # Arc
        p.setPen(QPen(QColor(0, 220, 255, 180), 2.5,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(cx-r+5, cy-r+5, (r-5)*2, (r-5)*2,
                  int(self._angle*16), int(105*16))

        # "J"
        f = QFont("Segoe UI", 13, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QPen(QColor(0, 220, 255, 230)))
        p.drawText(QRect(0, 0, 60, 60), Qt.AlignmentFlag.AlignCenter, "J")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def show_ball(self):
        self.setVisible(True)
        self.raise_()

    def hide_ball(self):
        self.setVisible(False)


# ═══════════════════════════════════════════════════════════════════════════
# WORKER THREADS (V8 style — non-blocking)
# ═══════════════════════════════════════════════════════════════════════════
class BrainWorker(QThread):
    result_ready = pyqtSignal(str, list)
    error_occurred = pyqtSignal(str)

    def __init__(self, brain, text: str, task_hint: str = "chat"):
        super().__init__()
        self.brain = brain
        self.text = text
        self.hint = task_hint

    def run(self):
        try:
            text, actions = self.brain.process(self.text, self.hint)
            self.result_ready.emit(text, actions)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ListenWorker(QThread):
    recognised = pyqtSignal(str)
    failed = pyqtSignal()

    def __init__(self, stt):
        super().__init__()
        self.stt = stt

    def run(self):
        try:
            text = self.stt.listen_once(timeout=5.0, phrase_limit=10.0)
            if text:
                self.recognised.emit(text)
            else:
                self.failed.emit()
        except Exception:
            self.failed.emit()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN WINDOW — V7 GUI + V8 Features (FIXED for task execution)
# ═══════════════════════════════════════════════════════════════════════════
class JarvisOmegaWindow(QMainWindow):
    speak_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)
    ai_reply_signal = pyqtSignal(str, list)
    ai_error_signal = pyqtSignal(str)
    stt_heard_signal = pyqtSignal(str)
    stt_fail_signal = pyqtSignal()

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.brain = None
        self.speaker = None
        self.listener = None
        self.automation = None
        self._hidden = False
        self._worker: Optional[BrainWorker] = None
        self._listen: Optional[ListenWorker] = None
        self._busy = False
        self._hinglish_mode = bool(settings.get("hinglish_display_mode", True))
        self._tts_enabled = True
        self._offline_mode = bool(settings.get("offline_mode", False))

        self._build_window()
        self._build_ui()
        self._setup_shortcuts()
        self._setup_tray()

        self.speak_signal.connect(self._on_speak)
        self.status_signal.connect(lambda t, k: self.statusbar.set(t, k))
        self.ai_reply_signal.connect(self._on_ai_reply)
        self.ai_error_signal.connect(self._on_ai_error)
        self.stt_heard_signal.connect(self._on_stt_heard)
        self.stt_fail_signal.connect(self._on_stt_fail)

        # Load modules after window is shown
        QTimer.singleShot(300, self._init_modules)

    # ── window setup ─────────────────────────────────────────────────────
    def _build_window(self):
        self.setWindowTitle("JARVIS OMEGA V8")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)

        # Background
        self.starfield = StarfieldWidget(root)
        self.starfield.setGeometry(root.rect())

        # Content layer
        self.content = QWidget(root)
        self.content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.content.setGeometry(root.rect())

        c_lay = QVBoxLayout(self.content)
        c_lay.setContentsMargins(40, 60, 40, 40)
        c_lay.addStretch(2)

        centre = QWidget()
        centre.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cl = QVBoxLayout(centre)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(10)

        self.reactor = ArcReactor(centre, size=200)
        cl.addWidget(self.reactor, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clock = ClockLabel(centre)
        cl.addWidget(self.clock, alignment=Qt.AlignmentFlag.AlignCenter)

        self.date = DateLabel(centre)
        cl.addWidget(self.date, alignment=Qt.AlignmentFlag.AlignCenter)

        self.hint = QLabel("Say 'Hey JARVIS' or press SPACE")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hint.setStyleSheet(
            "color:#2a4858;font-family:'Segoe UI';font-size:11px;"
            "letter-spacing:2px;background:transparent;margin-top:18px;")
        cl.addWidget(self.hint)

        c_lay.addWidget(centre, alignment=Qt.AlignmentFlag.AlignCenter)
        c_lay.addStretch(3)

        self.statusbar = StatusBar()
        c_lay.addWidget(self.statusbar)

        # Floating panels
        self.output = OutputPanel(root)
        self.output.setFixedSize(390, 440)

        self.chat = ChatPanel(root)
        self.chat.setFixedSize(510, 390)
        self.chat.mic_btn.clicked.connect(self._toggle_voice)
        self.chat.command_entered.connect(self.process_command)

        self.ball = AssistantBall(root)
        self.ball.clicked.connect(self._toggle_hidden)

        self._place_panels()

        # Z order
        self.content.raise_()
        self.chat.raise_()
        self.output.raise_()
        self.ball.raise_()

    def _place_panels(self):
        W, H = self.width(), self.height()
        mid_y = (H - 390) // 2 + 10
        if hasattr(self, "chat"):
            self.chat.move(W - 510 - 20, mid_y)
        if hasattr(self, "output"):
            self.output.move(20, (H - 440) // 2 + 10)
        if hasattr(self, "ball"):
            self.ball.move(W - 76, H - 76)

    # ── shortcuts ─────────────────────────────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._toggle_hidden)
        QShortcut(QKeySequence("Space"), self).activated.connect(self._toggle_voice)
        QShortcut(QKeySequence("Ctrl+J"), self).activated.connect(self._show_chat)
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self._hide_panels)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self._quit)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._quick_screenshot)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._show_settings)

    # ── system tray ───────────────────────────────────────────────────────
    def _setup_tray(self):
        px = QPixmap(48, 48)
        px.fill(QColor(0, 0, 0, 0))
        pr = QPainter(px)
        pr.setRenderHint(QPainter.RenderHint.Antialiasing)
        pr.setPen(QPen(C_CYAN, 2.5))
        pr.drawEllipse(5, 5, 38, 38)
        f = QFont("Segoe UI", 13, QFont.Weight.Bold)
        pr.setFont(f)
        pr.setPen(QPen(C_CYAN))
        pr.drawText(QRect(0, 0, 48, 48), Qt.AlignmentFlag.AlignCenter, "J")
        pr.end()

        self.tray = QSystemTrayIcon(QIcon(px), self)
        m = QMenu()
        m.addAction("Show / Hide", self._toggle_hidden)
        m.addAction("Chat", self._show_chat)
        m.addAction("Settings", self._show_settings)
        m.addSeparator()
        m.addAction("Quit", self._quit)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(
            lambda r: self._show_all()
            if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    # ── module init ───────────────────────────────────────────────────────
    def _init_modules(self):
        def _load():
            # Brain
            try:
                from core.brain import JarvisBrain
                self.brain = JarvisBrain(self.settings)
                self.status_signal.emit("BRAIN READY", "success")
            except Exception as e:
                self.status_signal.emit(f"BRAIN ERR", "error")
                print(f"[WIN] brain error: {e}")

            # TTS
            try:
                from speech.tts_engine import TTSEngine
                self.speaker = TTSEngine(self.settings)
            except Exception as e:
                print(f"[WIN] TTS error: {e}")

            # STT
            try:
                from speech.stt_engine import STTEngine
                self.listener = STTEngine(self.settings)
                print("[WIN] STT loaded successfully")
            except Exception as e:
                print(f"[WIN] STT error: {e}")
                self.status_signal.emit("STT ERROR — check console", "error")

            # Automation — FIXED: Use correct class name "Automation" not "AutomationController"
            try:
                from tools.automation import Automation
                self.automation = Automation()
                if self.brain:
                    self.brain.automation = self.automation
                print("[WIN] Automation loaded successfully")
            except Exception as e:
                print(f"[WIN] automation error: {e}")

            self.status_signal.emit("READY", "normal")

        threading.Thread(target=_load, daemon=True, name="module-init").start()

    # ── visibility ────────────────────────────────────────────────────────
    def _toggle_hidden(self):
        if self._hidden:
            self._show_all()
        else:
            self._hide_to_ball()

    def _hide_to_ball(self):
        self._hidden = True
        self.chat.hide_panel()
        self.output.hide_panel()
        self.content.setVisible(False)
        self.statusbar.setVisible(False)
        self.ball.show_ball()

    def _show_all(self):
        self._hidden = False
        self.ball.hide_ball()
        self.content.setVisible(True)
        self.statusbar.setVisible(True)
        self.raise_()
        self.activateWindow()

    def _show_chat(self):
        if self._hidden:
            self._show_all()
        self.chat.show_panel()

    def _hide_panels(self):
        self.chat.hide_panel()
        self.output.hide_panel()

    def _show_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.get_settings()
            self._hinglish_mode = new_settings["hinglish_display_mode"]
            self._offline_mode = new_settings["offline_mode"]
            self._tts_enabled = new_settings["tts_enabled"]
            self.settings["hinglish_display_mode"] = self._hinglish_mode
            self.settings["offline_mode"] = self._offline_mode
            if self.brain:
                try:
                    self.brain.router.s["offline_mode"] = self._offline_mode
                except Exception:
                    pass
            mode = "Offline" if self._offline_mode else "Online"
            self.chat.add_message(f"Mode: {mode} | Hinglish: {'ON' if self._hinglish_mode else 'OFF'} | TTS: {'ON' if self._tts_enabled else 'OFF'}", "SYSTEM")

    # ── voice ─────────────────────────────────────────────────────────────
    def _toggle_voice(self):
        if self._busy:
            return
        if not self.listener:
            self.statusbar.set("STT NOT AVAILABLE", "error")
            self.chat.add_message("Speech recognition not available. Check console for errors.", "SYSTEM")
            return
        if self.listener.is_listening:
            self.listener.stop_listening()
            self.reactor.set_mode("idle")
            self.statusbar.set("READY")
            self._reset_mic_btn()
        else:
            self._show_chat()
            self.reactor.set_mode("listening")
            self.statusbar.set("LISTENING…", "warning")
            self.chat.add_listening()
            self.chat.mic_btn.setText("🔴")
            self._listen = ListenWorker(self.listener)
            self._listen.recognised.connect(self.stt_heard_signal.emit)
            self._listen.failed.connect(self.stt_fail_signal.emit)
            self._listen.start()

    def _reset_mic_btn(self):
        self.chat.mic_btn.setText("🎤")

    def _on_stt_heard(self, text: str):
        self._reset_mic_btn()
        self.reactor.set_mode("thinking")
        self.statusbar.set("PROCESSING…", "warning")
        self._show_chat()
        self.chat.add_message(text, "USER")
        self.process_command(text)

    def _on_stt_fail(self):
        self._reset_mic_btn()
        self.reactor.set_mode("idle")
        self.statusbar.set("READY")
        self.chat.add_message("Kuch suna nahi — dobara koshish karein (mic button dabayein)", "SYSTEM")

    # ── command processing ────────────────────────────────────────────────
    def process_command(self, text: str):
        if not self.brain:
            self.chat.add_message("Brain still loading, Sir. Please wait.", "JARVIS")
            return
        if self._busy:
            return

        self._busy = True
        self.reactor.set_mode("thinking")
        self.statusbar.set("THINKING…", "warning")
        self._show_chat()
        self.chat.add_thinking()

        # Detect task type
        hint = "chat"
        tl = text.lower()
        if any(w in tl for w in ["search", "find", "google", "news", "latest", "who is"]):
            hint = "search"
        elif any(w in tl for w in ["screen", "read screen", "what's on screen", "see screen"]):
            hint = "screen"

        self._worker = BrainWorker(self.brain, text, hint)
        self._worker.result_ready.connect(self.ai_reply_signal.emit)
        self._worker.error_occurred.connect(self.ai_error_signal.emit)
        self._worker.finished.connect(self._on_brain_done)
        self._worker.start()

    def _on_brain_done(self):
        self._busy = False

    def _on_ai_reply(self, response: str, actions: list):
        # Remove "Thinking…" line
        cur = self.chat.display.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.select(QTextCursor.SelectionType.LineUnderCursor)
        if "Thinking…" in cur.selectedText():
            cur.removeSelectedText()
            cur.deletePreviousChar()

        # Display in Hinglish if enabled
        try:
            from core.brain import hindi_to_hinglish
            disp = hindi_to_hinglish(response) if self._hinglish_mode else response
        except Exception:
            disp = response

        self.chat.add_message(disp, "JARVIS")

        # TTS
        if self._tts_enabled and self.speaker:
            self.speak_signal.emit(response)

        # Execute actions — FIXED: Properly call automation.execute() with action dict
        if self.automation and actions:
            self.output.add_cmd(f"{len(actions)} action(s) executing…", True)
            for act in actions:
                # Pass the FULL action dict to execute() — not separate name/target
                try:
                    ok, msg = self.automation.execute(act)
                    self.chat.add_message(msg, "ACTION_OK" if ok else "ACTION_FAIL")
                    self.output.add_cmd(f"{act.get('action','?')} → {msg}", ok)

                    # Handle screenshot specially
                    if act.get("action") == "screenshot" and ok:
                        # msg contains the path or success message
                        # Try to extract path from msg
                        if "save hua" in msg:
                            # Screenshot was saved, try to show it
                            import glob
                            shots_dir = BASE / "data" / "screenshots"
                            if shots_dir.exists():
                                files = sorted(shots_dir.glob("*.png"))
                                if files:
                                    self.show_output_image(str(files[-1]), "Screenshot")

                    # Handle read_screen specially
                    elif act.get("action") == "read_screen" and ok:
                        self.show_output_text(msg, "screen")

                except Exception as e:
                    self.chat.add_message(f"Action failed: {e}", "ACTION_FAIL")
                    self.output.add_cmd(f"{act.get('action','?')} → Error: {e}", False)

        self.statusbar.set("READY")
        self.reactor.set_mode("idle")

    def _on_ai_error(self, err: str):
        self.chat.add_message(f"Error: {err}", "SYSTEM")
        self.statusbar.set("ERROR", "error")
        self.reactor.set_mode("idle")
        self._busy = False

    def _on_speak(self, text: str):
        self.reactor.set_mode("speaking")
        self.statusbar.set("SPEAKING", "success")
        if self.speaker:
            def _do_speak():
                try:
                    self.speaker.speak(text)
                except Exception as e:
                    print(f"[TTS] Speak error: {e}")
                finally:
                    self.statusbar.set("READY")
                    self.reactor.set_mode("idle")
            threading.Thread(target=_do_speak, daemon=True).start()
        else:
            QTimer.singleShot(2500, lambda: self.statusbar.set("READY"))
            QTimer.singleShot(3200, lambda: self.reactor.set_mode("idle"))

    # ── output helpers ───────────────────────────────────────────────────
    def show_output_image(self, path_or_pixmap, caption: str = ""):
        if self._hidden:
            self._show_all()
        self.output.add_image(path_or_pixmap, caption)

    def show_output_text(self, text: str, tab: str = "INFO"):
        if self._hidden:
            self._show_all()
        self.output.add_text(text, tab)

    # ── quick screenshot shortcut ─────────────────────────────────────────
    def _quick_screenshot(self):
        if self.automation:
            ok, msg = self.automation.execute({"action": "screenshot", "target": ""})
            self.chat.add_message(msg, "JARVIS" if ok else "SYSTEM")

    # ── resize / drag / quit ──────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        cw = self.centralWidget()
        if cw:
            cw.setGeometry(self.rect())
        for w in (self.starfield, self.content):
            if w:
                w.setGeometry(self.rect())
        self._place_panels()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if (e.buttons() == Qt.MouseButton.LeftButton
            and hasattr(self, "_drag_pos")):
            self.move(self.pos() +
                      e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def closeEvent(self, e):
        e.ignore()
        self.hide()

    def _quit(self):
        self.tray.hide()
        if self.speaker:
            try:
                self.speaker.shutdown()
            except Exception:
                pass
        QApplication.quit()