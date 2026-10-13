
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QSpinBox, QLabel, QTextEdit,
    QFileDialog, QSplitter, QGroupBox, QTextBrowser, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase

import sys

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH

from LLM import LLMSession, LLMApi, LLMRequest, LLMResponse, Message

from APP.workers import AskWorker


GREETING_TEXT = """
# 👋 Привет!

Я — **ИИ-ассистент** этого приложения. Готов помочь с вопросами, текстами, кодом, объяснениями и всем, что придёт в голову.

# Моя модель 🦾 : {model}

## Что я умею

- 💬 Отвечать на вопросы — от бытовых до технических
- ✍️ Помогать с текстами: письма, статьи, резюме, документация
- 🧑‍💻 Разбираться в коде: объяснить, найти баг, предложить рефактор
- 📚 Объяснять сложное простыми словами
- 🌍 Переводить и адаптировать под аудиторию

## Чего ждать не стоит

- ❌ Я не имею доступа к интернету в реальном времени
- ❌ Не сохраняю данные между сессиями (если не сказано иное)
- ❌ Могу ошибаться — проверяй важное

## Формат ответов

Отвечаю в **Markdown**: заголовки, списки, блоки кода, таблицы — всё для удобного чтения.

---

**С чего начнём?** Просто напиши свой вопрос 👇
"""
WAITING_TEXT = """
### 🤔 Обрабатываю запрос...

- 📖 Читаю контекст
- 🧠 Формулирую ответ
- ✍️ Оформляю в Markdown

_Это может занять несколько секунд._
"""


class LLMDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.llm_session = LLMSession(LLMApi())
        self._worker: AskWorker | None = None
        
        self.setWindowTitle("ИИ-помощник")

        LLM_MIN_H,  LLM_MAX_H  = 150, 430
        LINE_MIN_H, LINE_MAX_H = 20,  200
        GAP        = 20
        TOP_MARGIN = 5   # верхний отступ внутри контейнера `top`

        # --- Кнопка (нужна раньше — её высота задаёт минимум QTextEdit) ---
        self.btn_send = QPushButton("Отправить 📨")
        self.btn_send.clicked.connect(self._send_prompt)
        self.btn_send.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        hint = self.btn_send.sizeHint()
        btn_h = hint.height()
        btn_w = max(hint.width(), btn_h + 40)   # ширина > высоты
        self.btn_send.setMinimumSize(btn_w, btn_h)

        line_min = max(LINE_MIN_H, btn_h)       # реальный минимум для QTextEdit

        # Теперь границы окна честно совпадают с суммой границ детей.
        self.setMinimumSize(800, LLM_MIN_H + TOP_MARGIN + line_min  + GAP)
        self.setMaximumSize(960, LLM_MAX_H + TOP_MARGIN + LINE_MAX_H + GAP)
        self.resize(960, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        outter_splitter = QSplitter(Qt.Orientation.Vertical)
        outter_splitter.setChildrenCollapsible(False)
        outter_splitter.setHandleWidth(GAP)
        
        # --- Tool bar ---
        tool_bar = QHBoxLayout()
        
        self.btn_choice = QPushButton("Выбрать 👆")
        self.btn_choice.setToolTip(
                    "Выбрать другую сессию диалога"
                )
        
        self.btn_reset = QPushButton("Сбросить 🔄")
        self.btn_reset.setToolTip(
                            "Очистить текущий диалог(Т.е поменять на новую 'пустую' сессию)"
                        )
        
        tool_bar.addWidget(self.btn_choice)
        tool_bar.addWidget(self.btn_reset)
        tool_bar.addStretch(1)
        tool_bar.setContentsMargins(5, 0, 0, 0)
        
        # --- Текст LLM ---
        self.llm_label = QTextBrowser()
        self.llm_label.setPlaceholderText("Не менее уютное место для ответа LLM'ки :)")
        self.llm_label.setMarkdown(GREETING_TEXT.format(model=self.llm_session.base_model))
        self.llm_label.setOpenExternalLinks(True)
        self.llm_label.setMinimumHeight(LLM_MIN_H)
        self.llm_label.setMaximumHeight(LLM_MAX_H)

        top_widget = QWidget()
        # КЛЮЧЕВОЕ: контейнер тоже не может быть выше, чем llm_label + его отступы.
        top_widget.setMaximumHeight(LLM_MAX_H + TOP_MARGIN)
        lay = QVBoxLayout(top_widget)
        lay.setContentsMargins(5, TOP_MARGIN, 5, 0)
        lay.addWidget(self.llm_label)

        # --- QTextEdit ---
        font = QFont()
        font.setFamilies(["Segoe UI", "Inter", "Noto Sans", "sans-serif"])  # fallback-цепочка
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Normal)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        
        self.prompt_line = QTextEdit()
        self.prompt_line.setPlaceholderText("Уютное место для вашего промта ^_^")
        self.prompt_line.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.prompt_line.setMinimumHeight(line_min)
        self.prompt_line.setMaximumHeight(LINE_MAX_H)
        self.prompt_line.setFont(font)

        # --- Нижняя панель ---
        bottom = QWidget()
        bottom.setMaximumHeight(LINE_MAX_H)

        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(10, 0, 0, 5)
        bottom_layout.setSpacing(6)
        bottom_layout.addWidget(self.prompt_line, 1)
        bottom_layout.addWidget(
            self.btn_send, 0, Qt.AlignmentFlag.AlignVCenter
        )

        # ---------- сборка ----------
        outter_splitter.addWidget(top_widget)
        outter_splitter.addWidget(bottom)
        outter_splitter.setStretchFactor(0, 1)
        outter_splitter.setStretchFactor(1, 0)
        outter_splitter.setSizes([360, 120])
        
        root.addLayout(tool_bar)
        root.addWidget(outter_splitter, 1)
    
    def _on_answer(self, answer: str):
        self.llm_label.setMarkdown(answer)

    def _on_error(self, message: str):
        self.llm_label.setMarkdown(f"### ⚠️ Ошибка\n\n```\n{message}\n```")

    def _on_finished(self):
        self.prompt_line.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.prompt_line.setFocus()
        self._worker = None   
    
    def _send_prompt(self):
        prompt = self.prompt_line.toPlainText().strip()
        if not prompt:
            return
        
        self.prompt_line.clear()
        
        self.llm_label.setMarkdown(WAITING_TEXT) #Ставим заглушку и запрещаем доступ к вводу и отправке
        self.prompt_line.setEnabled(False)
        self.btn_send.setEnabled(False)
        
        request = LLMRequest(
            prompt=Message("user", prompt),
            session_id=self.llm_session.id,
        )
        
        self._worker = AskWorker(self.llm_session, request, parent=self)
        self._worker.done.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = LLMDialog()
    dialog.show()
    sys.exit(app.exec())