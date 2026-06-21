"""
gui/orb_window.py — JARVIS OMEGA V9
Floating transparent assistant orb. No background, no borders, no taskbar icon.
Uses Qt6 with WA_TranslucentBackground + FramelessWindowHint + Tool flag.
ESC key toggles orb mode (only when orb is active).
"""
from __future__ import annotations

import sys, math, time, threading
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QIcon, QPixmap, QCursor
)

BASE = Path(__file__).resolve().parent.parent

# ═════════════════════════════════════════════════════════════════════════════
# ORB WIDGET — The floating ball
# ═════════════════════════════════════════════════════════════════════════════
class AssistantOrb(QWidget):
    """Transparent floating orb with animations for different states."""

    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    right_clicked = pyqtSignal()

    def __init__(self, size: int = 120, parent=None):
        super().__init__(parent)
        self.orb_size = size
        self.setFixedSize(size, size)

        # CRITICAL: Transparency and frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # No taskbar icon
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._angle = 0.0
        self._pulse = 0.0
        self._mode = "idle"
        self._dragging = False
        self._drag_pos = QPoint()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)

        self._load_position()

    def _load_position(self):
        pos_file = BASE / "data" / "orb_position.json"
        try:
            if pos_file.exists():
                import json
                pos = json.loads(pos_file.read_text())
                self.move(pos["x"], pos["y"])
            else:
                screen = QApplication.primaryScreen().geometry()
                self.move(screen.width() - self.orb_size - 20, 
                         screen.height() - self.orb_size - 60)
        except Exception:
            pass

    def _save_position(self):
        pos_file = BASE / "data" / "orb_position.json"
        try:
            import json
            pos_file.write_text(json.dumps({"x": self.x(), "y": self.y()}))
        except Exception:
            pass

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def _animate(self):
        speeds = {
            "idle": 1.5,
            "listening": 4.0,
            "thinking": 6.0,
            "speaking": 5.0,
            "error": 2.0
        }
        self._angle = (self._angle + speeds.get(self._mode, 2.0)) % 360
        self._pulse = (self._pulse + 0.06) % 6.28
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = cy = self.orb_size // 2
        radius = cx - 4

        colors = {
            "idle": (QColor(0, 180, 255), QColor(0, 100, 200)),
            "listening": (QColor(0, 255, 120), QColor(0, 150, 80)),
            "thinking": (QColor(255, 180, 0), QColor(200, 120, 0)),
            "speaking": (QColor(100, 200, 255), QColor(50, 150, 220)),
            "error": (QColor(255, 60, 60), QColor(180, 30, 30))
        }
        primary, secondary = colors.get(self._mode, colors["idle"])

        pulse = 0.85 + 0.15 * math.sin(self._pulse)

        # Outer glow
        for i in range(6, 0, -1):
            alpha = int(25 * pulse / i)
            grad = QRadialGradient(cx, cy, radius * (1 + i * 0.15))
            grad.setColorAt(0, QColor(primary.red(), primary.green(), primary.blue(), alpha))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(cx - radius * (1 + i * 0.15)),
                int(cy - radius * (1 + i * 0.15)),
                int(radius * 2 * (1 + i * 0.15)),
                int(radius * 2 * (1 + i * 0.15))
            )

        # Main orb body
        body_grad = QRadialGradient(cx - radius*0.3, cy - radius*0.3, radius * 1.2)
        body_grad.setColorAt(0, QColor(30, 60, 100, 220))
        body_grad.setColorAt(0.7, QColor(10, 25, 50, 200))
        body_grad.setColorAt(1, QColor(5, 10, 20, 180))

        painter.setBrush(QBrush(body_grad))
        painter.setPen(QPen(primary, 2))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Inner energy ring
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 120), 1.5))
        inner_r = int(radius * 0.7)
        painter.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        # Rotating arc
        painter.setPen(QPen(primary, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        arc_span = 100 if self._mode == "idle" else 140
        painter.drawArc(
            cx - radius + 8, cy - radius + 8,
            (radius - 8) * 2, (radius - 8) * 2,
            int(self._angle * 16), int(arc_span * 16)
        )

        # Counter-rotating inner arc
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 80), 2))
        painter.drawArc(
            cx - inner_r + 4, cy - inner_r + 4,
            (inner_r - 4) * 2, (inner_r - 4) * 2,
            int(-self._angle * 1.5 * 16), int(60 * 16)
        )

        # Center core
        core_r = 8 * pulse
        core_grad = QRadialGradient(cx, cy, core_r * 2)
        core_grad.setColorAt(0, primary)
        core_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(float(cx), float(cy)), core_r, core_r)

        # Mode label
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(200, 230, 255, 180)))
        label = self._mode.upper()
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(label)
        painter.drawText(cx - tw // 2, cy + radius - 8, label)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() == Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._save_position()

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def enterEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def leaveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

# ═════════════════════════════════════════════════════════════════════════════
# MINIMAL CHAT POPUP
# ═════════════════════════════════════════════════════════════════════════════
class OrbChatPopup(QFrame):
    command_entered = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(400, 300)
        self._build_ui()
        self._opacity = 0
        self._apply_opacity()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.setStyleSheet("""
            QFrame {
                background: rgba(10, 15, 30, 220);
                border: 1px solid rgba(0, 200, 255, 80);
                border-radius: 16px;
            }
            QTextEdit {
                background: transparent;
                color: #b8d4ee;
                font-family: 'Segoe UI';
                font-size: 12px;
                border: none;
            }
            QLineEdit {
                background: rgba(0, 20, 50, 180);
                color: #9ec8ef;
                border: 1px solid rgba(0, 200, 255, 60);
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton {
                background: rgba(0, 150, 200, 120);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(0, 180, 230, 180); }
        """)

        header = QHBoxLayout()
        title = QLabel("◈ JARVIS ◈")
        title.setStyleSheet("color: #00c8ff; font-size: 11px; font-weight: bold; letter-spacing: 3px;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide_popup)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setMaximumBlockCount(100)
        layout.addWidget(self.display)

        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Command boliye ya type karein...")
        self.input.returnPressed.connect(self._send)
        input_row.addWidget(self.input)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedWidth(40)
        input_row.addWidget(self.mic_btn)

        send_btn = QPushButton("➤")
        send_btn.setFixedWidth(40)
        send_btn.clicked.connect(self._send)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

    def _apply_opacity(self):
        self.setWindowOpacity(self._opacity / 255)

    def show_near(self, orb_rect: QRect):
        screen = QApplication.primaryScreen().geometry()
        x = orb_rect.left() - self.width() - 10
        if x < 10:
            x = orb_rect.right() + 10
        y = orb_rect.top()
        if y + self.height() > screen.height():
            y = screen.height() - self.height() - 10
        self.move(x, y)
        self.show()
        self._fade_in()

    def _fade_in(self):
        self._opacity = 0
        QTimer.singleShot(16, self._do_fade_in)

    def _do_fade_in(self):
        self._opacity = min(255, self._opacity + 25)
        self._apply_opacity()
        if self._opacity < 255:
            QTimer.singleShot(16, self._do_fade_in)

    def hide_popup(self):
        self._fade_out()

    def _fade_out(self):
        self._opacity = max(0, self._opacity - 25)
        self._apply_opacity()
        if self._opacity > 0:
            QTimer.singleShot(16, self._fade_out)
        else:
            self.hide()
            self.closed.emit()

    def add_message(self, text: str, sender: str = "JARVIS"):
        ts = time.strftime("%H:%M")
        colors = {"JARVIS": "#00c8ff", "USER": "#55ee88", "SYSTEM": "#888888", "ACTION": "#aaffcc"}
        color = colors.get(sender, "#b8d4ee")
        self.display.append(f'<span style="color:#3a5868">[{ts}]</span> <span style="color:{color}"><b>{sender}:</b> {text}</span>')

    def _send(self):
        txt = self.input.text().strip()
        if txt:
            self.add_message(txt, "USER")
            self.input.clear()
            self.command_entered.emit(txt)

# ═════════════════════════════════════════════════════════════════════════════
# ORB MAIN WINDOW — Controller
# ═════════════════════════════════════════════════════════════════════════════
class OrbMainWindow(QMainWindow):
    speak_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)
    process_command_signal = pyqtSignal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self._setup_orb()
        self._setup_popup()
        self._setup_tray()
        self._setup_shortcuts()

        self.brain = None
        self.speaker = None
        self.listener = None
        self.automation = None
        self.learning = None

        QTimer.singleShot(300, self._init_modules)

    def _setup_orb(self):
        size = self.settings.get("V9_NEW", {}).get("esc_orb_size", 120)
        self.orb = AssistantOrb(size=size)
        self.orb.clicked.connect(self._on_orb_click)
        self.orb.double_clicked.connect(self._on_orb_double_click)
        self.orb.right_clicked.connect(self._show_context_menu)
        self.orb.show()

    def _setup_popup(self):
        self.popup = OrbChatPopup()
        self.popup.command_entered.connect(self._on_command)
        self.popup.closed.connect(self._on_popup_closed)
        self.popup.hide()

    def _setup_tray(self):
        px = QPixmap(48, 48)
        px.fill(QColor(0, 0, 0, 0))
        pr = QPainter(px)
        pr.setRenderHint(QPainter.RenderHint.Antialiasing)
        pr.setPen(QPen(QColor(0, 200, 255), 2))
        pr.drawEllipse(4, 4, 40, 40)
        pr.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        pr.setPen(QPen(QColor(0, 200, 255)))
        pr.drawText(QRect(0, 0, 48, 48), Qt.AlignmentFlag.AlignCenter, "J")
        pr.end()

        self.tray = QSystemTrayIcon(QIcon(px), self)
        menu = QMenu()
        menu.addAction("Show Chat", self._show_chat)
        menu.addAction("Settings", self._show_settings)
        menu.addSeparator()
        menu.addAction("Teach JARVIS", self._start_teaching)
        menu.addAction("Export Training Data", self._export_training)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._show_chat() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self.tray.show()

    def _setup_shortcuts(self):
        pass

    def _init_modules(self):
        def _load():
            try:
                from core.brain import JarvisBrain
                self.brain = JarvisBrain(self.settings)
                self.popup.add_message("JARVIS V9 ready. Click orb to speak.", "SYSTEM")
            except Exception as e:
                self.popup.add_message(f"Brain error: {e}", "SYSTEM")

            try:
                from speech.tts_engine import TTSEngine
                self.speaker = TTSEngine(self.settings)
            except Exception as e:
                print(f"[ORB] TTS error: {e}")

            try:
                from speech.stt_engine import STTEngine
                self.listener = STTEngine(self.settings)
            except Exception as e:
                print(f"[ORB] STT error: {e}")

            try:
                from tools.automation import Automation
                self.automation = Automation(self.settings)
                if self.brain:
                    self.brain.automation = self.automation
            except Exception as e:
                print(f"[ORB] Automation error: {e}")

            try:
                from learning.trainer import get_learning_hub
                self.learning = get_learning_hub()
                if self.brain:
                    prefs = self.learning.get_system_prompt_additions()
                    if prefs:
                        print(f"[LEARN] Injected preferences: {prefs[:100]}...")
            except Exception as e:
                print(f"[ORB] Learning hub error: {e}")

        threading.Thread(target=_load, daemon=True).start()

    def _on_orb_click(self):
        if self.popup.isVisible():
            self.popup.hide_popup()
        else:
            self._show_chat()
            self._start_listening()

    def _on_orb_double_click(self):
        if self.automation:
            ok, msg = self.automation.execute({"action": "screenshot", "target": ""})
            self.popup.add_message(msg, "JARVIS" if ok else "SYSTEM")

    def _show_chat(self):
        if not self.popup.isVisible():
            self.popup.show_near(self.orb.frameGeometry())
            self.orb.set_mode("idle")

    def _on_popup_closed(self):
        self.orb.set_mode("idle")

    def _on_command(self, text: str):
        if not self.brain:
            self.popup.add_message("Still loading, Sir...", "JARVIS")
            return

        self.orb.set_mode("thinking")
        self.popup.add_message("Thinking...", "SYSTEM")

        if self.learning:
            skill_actions = self.learning.process_user_input(text)
            if skill_actions:
                self.popup.add_message("Skill matched! Executing...", "JARVIS")
                self._execute_actions(skill_actions, text)
                return

        def _process():
            try:
                response, actions = self.brain.process(text)
                self.process_command_signal.emit(response)
                if actions and self.automation:
                    self._execute_actions(actions, text)
            except Exception as e:
                self.status_signal.emit(str(e), "error")

        threading.Thread(target=_process, daemon=True).start()

    def _execute_actions(self, actions: list, context: str):
        for act in actions:
            if self.automation:
                ok, msg = self.automation.execute(act)
                self.popup.add_message(msg, "ACTION" if ok else "SYSTEM")
                if self.learning:
                    self.learning.report_result(act, context, ok)

    def _start_listening(self):
        if self.listener:
            self.orb.set_mode("listening")
            self.popup.add_message("Listening...", "SYSTEM")

    def _start_teaching(self):
        self.popup.add_message("Teaching mode: Say 'When I say X, do Y'", "SYSTEM")

    def _export_training(self):
        if self.learning:
            path = self.learning.exporter.export_for_ollama()
            self.popup.add_message(f"Training data exported to: {path}", "SYSTEM")

    def _show_settings(self):
        self.popup.add_message("Settings: Use config/settings.json", "SYSTEM")

    def _show_context_menu(self):
        menu = QMenu()
        menu.addAction("Chat", self._show_chat)
        menu.addAction("Screenshot", self._on_orb_double_click)
        menu.addAction("Read Screen", self._read_screen)
        menu.addSeparator()
        menu.addAction("Hide", self.orb.hide)
        menu.addAction("Quit", self._quit)
        menu.exec(self.orb.mapToGlobal(QPoint(0, 0)))

    def _read_screen(self):
        try:
            from vision.screen_vision import get_screen_reader
            reader = get_screen_reader(self.settings)
            text = reader.read(use_ai=True)
            self.popup.add_message(text[:500], "JARVIS")
        except Exception as e:
            self.popup.add_message(f"Screen read error: {e}", "SYSTEM")

    def _quit(self):
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.orb.hide()
